# AI_RAG
Complete RAG setup file for AI model training. Ollama supported


## Setup - Linux (Python 3)
1. <code>cd [directory of use]</code>
2. <code>python -m venv venv</code>
3. <code>./venv/bin/pip install --upgrade pip</code>
4. <code>./venv/bin/pip install chromadb pypdf python-pptx tqdm requests pytesseract pdf2image pillow mwparserfromhell</code>
5. <code>./venv/bin/python Setup.py</code> (Setup file must be in the same folder with cd command)


## Parameters
_<code>./venv/bin/python Setup.py</code>_ <p>
<code>--model [ollama model name]</code> --> Example <code>./venv/bin/python Setup.py --model krikri-gpu:latest</code><br>
After load of model Setup.py support indexing from a database (.xml.bz2 dump), like Wikipedia.
**Example:** <br>💬 Question: wiki <br>📂 Path from .xml.bz2 dump: [full file path of .xml.bz2]

## Focus


## Credits
"All this code was written by [Claude](https://claude.ai) and [Gemini](https://gemini.google.com), while the idea and review were done by Kapelo Team, which consists of @Android_Creator5 and Aster."
