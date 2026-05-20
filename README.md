# AI Python RAG Setup
This project was created as part of our participation in the [18th Student Conference](https://www.synedrio.kmaked.eu/) (2026), which took place at [Noesis](https://www.noesis.edu.gr) and was organized by the [1st EK of Evosmos](https://ekevosmou.eu/). This work was completed by the students [Lefteris Trompakas](https://github.com/AndroidCreator5) and [Asteris Tsiboukas](https://github.com/Mr-sk1llZ), under the supervision of teachers Zoe Belli and George Arnaoutoglou.

## Setup - Linux (Python 3)
1. <code>cd [directory of use]</code>
2. <code>python -m venv venv</code>
3. <code>./venv/bin/pip install --upgrade pip</code> --only at install (one time)
4. <code>./venv/bin/pip install chromadb pypdf python-pptx tqdm requests pytesseract pdf2image pillow mwparserfromhell</code> --only at install (one time)
5. <code>./venv/bin/python Setup.py</code> (Setup file must be in the same folder with cd command)


## Parameters
<code>--model [ollama model name*]</code> --> Example <code>./venv/bin/python Setup.py --model krikri-gpu:latest</code><br>
After load of model Setup.py support indexing from a database (.xml.bz2 dump), like Wikipedia.
**Example:** <br>💬 Question: wiki <br>📂 Path from .xml.bz2 dump: [full file path of .xml.bz2]
<br>_*Ollama model name can be found be the execute of command <code>ollama list</code>_

## Abilities
- Support OCR from images, pdfs, pptx
- In the index, a selection is made between sources containing more theory and sources that primarily feature logical content (Mathematics - Computer Science). 'OneTime' refers to the folders containing  sources, meaning data that will be added to the model without indexing.<br>
- It supports the automatic extraction of files to the output folder.
- Multithread
- Progress check

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

### Credits
All this code was written by [Claude](https://claude.ai) and [Gemini](https://gemini.google.com), while the idea and review were done by **Kapelo Team**, which consists of [Lefteris Trompakas](https://github.com/AndroidCreator5) and [Asteris Tsiboukas](https://github.com/Mr-sk1llZ).
<br>__Python libraries: chromadb, pypdf, python-pptx, tqdm, requests, pytesseract, pdf2image, pillow, mwparserfromhell__
