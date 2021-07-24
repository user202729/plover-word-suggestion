from functools import lru_cache
from typing import List, Tuple, Optional



# define write and stop functions, console output
if 1:
	def write(content: str)->None:
		print(content, end="")

	def stop()->None:
		pass
else:
	from plover_textarea.extension import get_instance
	window_name=":plover_word_suggestion"

	def write(content: str)->None:
		get_instance().write(window_name, content)

	def stop()->None:
		get_instance().close(window_name)


disambiguation_stroke: str="R-RPB"


class Main:
	def __init__(self, engine)->None:
		self._engine=engine

	def start(self)->None:
		write("")
		self._engine.hook_connect("translated", self._on_translated)

	def _on_translated(self, _old, _new)->None:
		#Stroke(steno_keys).rtfcre
		translations=self._engine.translator_state.translations
		dictionaries=self._engine.dictionaries
		longest_key: int=dictionaries.longest_key
		if longest_key==0: return

		strokes: Tuple[str, ...]=tuple(stroke
				for translation in translations
				for stroke in translation.rtfcre
				)[-longest_key:]
		if strokes[-1]==disambiguation_stroke:
			return

		anything_written=False
		for i in range(len(strokes)):
			outline_original: Tuple[str, ...]=strokes[i:]
			outline=outline_original
			i_written=False
			for pad in range(1, longest_key-len(outline_original)+1):
				outline+=(disambiguation_stroke,)
				word: Optional[str]=dictionaries.lookup(outline)
				if word is None: break
				if not i_written:
					i_written=True
					write(f":: {len(outline_original)} last stroke(s):\n")
				outlines: List[Tuple[str, ...]]=dictionaries.reverse_lookup(word)
				outlines_=[
						"/".join(outline_)
						for outline_ in outlines
						if outline_[-1]!=disambiguation_stroke
						and len(outline_)<=len(outline)
						]
				comment=f"also {' | '.join(outlines_)}" if outlines_ else f"no alternatives"
				write(f"  + pad {pad}: {word} ({comment})\n")
				anything_written=True
		if anything_written:
			write("\n")


	def stop(self)->None:
		self._engine.hook_disconnect("translated", self._on_translated)
