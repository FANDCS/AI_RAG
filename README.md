# AI_RAG
Complete RAG setup file for AI model training. Ollama supported


## Setup - Linux (Python 3)
1. <code>cd [directory of use]</code>
2. <code>python -m venv venv</code>
3. <code>./venv/bin/pip install --upgrade pip</code>
4. <code>./venv/bin/pip install chromadb pypdf python-pptx tqdm requests pytesseract pdf2image pillow mwparserfromhell</code>
5. <code>./venv/bin/python Setup.py</code> (Setup file must be in the same folder with cd command)


## Parameters
<code>--model [ollama model name]</code> --> Example <code>./venv/bin/python Setup.py --model krikri-gpu:latest</code><br>
After load of model Setup.py support indexing from a database (.xml.bz2 dump), like Wikipedia.
**Example:** <br>💬 Question: wiki <br>📂 Path from .xml.bz2 dump: [full file path of .xml.bz2]

## Abilities
In the index, a selection is made between sources containing more theory and sources that primarily feature logical content (Mathematics - Computer Science). 'OneTime' refers to the folders containing  sources, meaning data that will be added to the model without indexing.<br>
It supports the automatic extraction of files to the output folder.

## Paths
**Full file path folder**<pre>
|-- AuthorizedMath/      (Sources with Math/Logic for indexing)
|-- AuthorizedThe/       (Sources with Theory for indexing)
|-- db/                  (ChromaDB database directory)
|-- materials/           (Materials/Documents storage)
|-- OneTimeMath/         (One-time-use Math sources - no indexing)
|-- OneTimeThe/          (One-time-use Theory sources - no indexing)
|-- Output/              (Automatic file extraction folder)
|-- venv/                (Python Virtual Environment)
|-- Modelfile            (Ollama configuration file)
|-- Modelfile.save       (Backup configuration file)
`-- Setup.py             (Main application script)</pre>

## Credits
All this code was written by [Claude](https://claude.ai) and [Gemini](https://gemini.google.com), while the idea and review were done by Kapelo Team, which consists of @AndroidCreator5 and Aster.
<br>__Python libraries: chromadb, pypdf, python-pptx, tqdm, requests, pytesseract, pdf2image, pillow, mwparserfromhell__
