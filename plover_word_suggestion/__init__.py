from functools import lru_cache
from typing import List

#from plover.stroke import Stroke

from .library import lookup_s, rtfcre_to_skeys
#, reverse_dictionary



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


MAX_STROKES=6

@lru_cache(maxsize=60)
def lookup_cached(rtfcre: str)->List[str]:
	return lookup_s(rtfcre_to_skeys(rtfcre))

class Main:
	def __init__(self, engine)->None:
		self._engine=engine

	def start(self)->None:
		write("")
		self._engine.hook_connect("translated", self._on_translated)

	def _on_translated(self, _old, _new)->None:
		#Stroke(steno_keys).rtfcre
		translations=self._engine.translator_state.translations
		strokes=[stroke
				for translation in translations
				for stroke in translation.rtfcre
				][-MAX_STROKES:]
		write("============\n")
		for i in range(len(strokes)):
			lookup_result=lookup_cached("/".join(strokes[i:]))

			if lookup_result:
				write(f":: {len(strokes)-i} last stroke(s):\n")
			for word in lookup_result[:15]:
				outlines=self._engine.dictionaries.reverse_lookup(word)
				outlines=[
						"/".join(outline)
						for outline in outlines]
				write(f">>> {word} : {' | '.join(outlines)}\n")
			if lookup_result:
				write("\n")


	def stop(self)->None:
		self._engine.hook_disconnect("translated", self._on_translated)
