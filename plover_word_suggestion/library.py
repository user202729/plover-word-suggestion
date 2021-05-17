#!/bin/python

import sys
import json
import itertools
from pathlib import Path
from typing import List, Dict, Optional, NamedTuple, Iterable, Set, Tuple, Sequence

import spectra_lexer
s=spectra_lexer.Spectra()

#the import takes a little too much time...
#the code below is only correct for some operating systems.

CONFIG_DIR=Path("~/.local/share/plover").expanduser()
if not CONFIG_DIR.is_dir():
	from plover.oslayer.config import CONFIG_DIR
	CONFIG_DIR=Path(CONFIG_DIR)
plover_dictionary_path=Path(CONFIG_DIR)/"main.json"

#main_dictionary_path=Path("/tmp/dict.json") # from https://github.com/didoesdigital/steno-dictionaries
main_dictionary_path=plover_dictionary_path
frequency_file_path=Path("/tmp/frequency.json")


# Setup:

from plover_stroke import BaseStroke

class Stroke(BaseStroke):
     pass

Stroke.setup(
    # System keys.
    '''
    #
    S- T- K- P- W- H- R-
    A- O-
    *
    -E -U
    -F -R -P -B -L -G -T -S -D -Z
    '''.split(),
    # Implicit hyphen keys (optional, automatically
    # deduced from system keys if not passed).
    'A- O- * -E -U'.split(),
    # Number bar key and numbers keys (optional).
    '#', {
    'S-': '1-',
    'T-': '2-',
    'P-': '3-',
    'H-': '4-',
    'A-': '5-',
    'O-': '0-',
    '-F': '-6',
    '-P': '-7',
    '-L': '-8',
    '-T': '-9',
    })



dictionary: Dict[str, str]=json.loads(main_dictionary_path.read_text(encoding='u8'))
words: List[str]=list(dictionary.values())

class Node: # (NamedTuple):
	#have: bool
	#children: Dict[str, "Node"]

	__slots__=["have", "children", "word"]

	def __init__(self, word)->None:
		self.have: bool=False
		self.children: Dict[str, Node]={}
		self.word: str=word # lower'ed!
	
	#@staticmethod
	#def empty()->"Node":
	#	return Node(False, {})

	def child(self, branch: str)->"Node":
		assert len(branch)==1
		if branch not in self.children:
			self.children[branch]=Node(self.word+branch)
		return self.children[branch]

root=Node("")
# store the trie of words, (!!) lower-cased

for word_lower in set(word.lower() for word in words):
	node=root
	for ch in word_lower: node=node.child(ch)
	assert not node.have
	node.have=True


rtfcre_to_skeys=s.analyzer._converter.rtfcre_to_skeys
skeys_to_rtfcre=s.analyzer._converter.skeys_to_rtfcre

rules=[
		("/", "")  # *need this rule to work
		]

common_briefs=set()

for rule in s.rules:
	if rule.is_word:
		common_briefs.add(rule.letters)
	elif rule.id in ["'", "-'s", "/", "+", "=", "*", "-", ".", ",", "?", "!", ":", ";", "...", " ",]:
		pass
	elif rule.info.startswith(("number ", "fraction ")):
		pass
	elif not (rule.is_reference or rule.is_stroke or rule.is_word):
		skeys = rtfcre_to_skeys(rule.keys)
		letters = rule.letters.lower()
		rules.append((skeys, letters))

# currently unordered is not provide.
# from key_layout.cson:
#
# > # A special key that may ignore steno order. This has a large performance and accuracy cost.
# > # Only the asterisk is typically used in such a way that this treatment is worth it.
# > "special": "*",
#
# Perhaps it might not work that well.
# ALG/R*EUPLT -> algorithm doesn't match in Spectra Lexer. (isn't the star supposed to match?)

def deduplicate(nodes: Iterable[Node])->List[Node]:
	return [*{id(node): node for node in nodes}.values()]

# does not mutate input `nodes`
def traverse(nodes: List[Node], letters: str)->List[Node]:
	if not letters: return nodes[:]
	for letter in letters:
		nodes=[
				next_node
				for node in nodes
				for next_node in (node.children.get(letter),)
				if next_node is not None
				]
	return nodes


# does not mutate input `nodes`
def skip_letters(nodes: List[Node])->List[Node]:
	return [*itertools.chain(
		nodes,
		*(
			traverse(nodes, letter)
			for letter in "aeiouy"
			)
		)]


if 1: # test
	assert not root.have

	z=traverse([root], "me")
	assert len(z)==1
	assert z[0].have

	z=traverse([root], "m")
	assert len(z)==1

	z=traverse(z, "e")
	assert len(z)==1
	assert z[0].have

	z=skip_letters(z)
	assert len(z)>=1
	assert z[0].have # dangerous...

	assert len(deduplicate(z))>=1


class State(NamedTuple):
	skeys_left: str
	node: Node




#of course this is the hard part :)

def lookup_1(skeys: str)->List[str]:


	# completely in-order algorithm
	# cannot match S*EUPBT to s-i-n-th, or R*EUPLT -> (algo)r-i-th-m, or even *EUPBG -> i-nk
	queue: List[List[Node]]=[
			[]
			for _ in range(len(skeys)+1)
			] 
	# [0]: full skeys
	# [1]: that removes the first character
	# etc.
	# until the end -> empty skeys.
	queue[0].append(root)


	for i in range(len(skeys)):
		nodes: List[Node]=deduplicate(queue[i])
		queue[i]=[]
		skeys_left=skeys[i:]
		for r_skeys, r_letters in rules:
			assert r_skeys
			if skeys_left.startswith(r_skeys):
				queue[i+len(r_skeys)].extend(
						skip_letters(traverse(nodes, r_letters))
						)

	return [
		node.word
		for node in queue[-1]
		if node.have]


def lookup_s(skeys: str)->List[str]:
	# algorithm that handles the star specially

	skeys="/".join(
			stroke.replace("*", "", 1)+"*" if "*" in stroke else stroke
			for stroke in skeys.split("/")
			)
	# now it isn't really skeys anymore, but for convenience it's still called skeys

	result: Set[str]=set()
	queue: List[State]=[]

	visited_states: Set[Tuple[str, int]]=set()
	def queue_add(skeys_left: str, node: Node)->None:
		hash_state=(skeys_left, id(node))
		if hash_state in visited_states: return # (is this check necessary?...)
		visited_states.add(hash_state)

		queue.append(State(skeys_left, node))

	queue_add(skeys, root)

	for skeys_left, node in queue:
		for r_skeys, r_letters in rules:
			assert r_skeys

			new_skeys_left: Optional[str]=None

			if skeys_left.startswith(r_skeys):
				match=True
				new_skeys_left=skeys_left[len(r_skeys):]

			elif "/" not in r_skeys and "*" in r_skeys:
				first_stroke_left: str
				rest_left: Sequence[str]
				first_stroke_left, *rest_left=skeys_left.split("/", maxsplit=1)
				if "*" in first_stroke_left:
					first_stroke_without_star=first_stroke_left.replace("*", "", 1)
					if first_stroke_without_star.startswith(r_skeys.replace("*", "", 1)):
						new_skeys_left=first_stroke_without_star[len(r_skeys)-1:]
						if rest_left:
							new_skeys_left+="/"+rest_left[0]

			if new_skeys_left is not None:
				for new_node in skip_letters(traverse([node], r_letters)):
					if new_skeys_left:
						queue_add(new_skeys_left, new_node)
					elif new_node.have:
						result.add(new_node.word)
	return [*result]


def interactive_prompt()->None:
	import readline
	while True:
		stroke=input("Enter a stroke (or stroke->word format): ")
		word=None
		temporary_have=False
		if "->" in stroke:
			stroke, word=stroke.split("->")
			word=word.strip()

			temporary_new_node=root

			# note that this might not be "new"
			# if the word is existing in the dictionary or is a prefix of one

			for ch in word.lower(): temporary_new_node=temporary_new_node.child(ch)
			if not temporary_new_node.have:
				temporary_have=True
				temporary_new_node.have=True

		stroke=stroke.replace("/", " ")
		stroke="/".join(stroke.split())
		skeys=rtfcre_to_skeys(stroke)

		lookup_result=lookup_s(skeys)

		preprompt=""
		if word is not None:
			preprompt="(+)" if word.lower() in lookup_result else "(?)"

		print(preprompt+">>>",
				" ".join(lookup_result[:20]) +
				(" (...)" if len(lookup_result)>20 else "")
				)

		if temporary_have:
			assert temporary_new_node.have
			temporary_new_node.have=False

			# memory leak: the new node is not deleted
			# not a problem.

def analysis()->None:
	from collections import defaultdict
	reverse_dictionary=defaultdict(list)
	for stroke, word in dictionary.items(): reverse_dictionary[word].append(stroke)

	frequency: Dict[str, float]=json.loads(
			frequency_file_path
			.read_text())
	count: int=0
	for word in frequency:
		if word not in common_briefs:
			for stroke in reverse_dictionary.get(word, ()):
				if word.lower() not in lookup_s(rtfcre_to_skeys(stroke)):
					print(stroke,
							#rtfcre_to_skeys(stroke),
							word,
							)
					count+=1
					#if count>=50: return


if __name__=="__main__":
	if sys.argv[1:]==["a"]:
		analysis()
	else:
		interactive_prompt()
