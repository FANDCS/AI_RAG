import os
import glob
import bz2
import chromadb
import requests
import json
import sys
import argparse
import logging
import re
import curses
from xml.etree import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from tqdm import tqdm

try:
    import mwparserfromhell
    HAS_MWPARSER = True
except ImportError:
    HAS_MWPARSER = False

# --- ΡΥΘΜΙΣΕΙΣ PATHS & HARDWARE ---
BASE_PATH = "/mnt/btrfsd/data/ModelTrainning/"
CHROMA_PATH = os.path.join(BASE_PATH, "db")
OUTPUT_PATH = os.path.join(BASE_PATH, "Output")

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
PARSING_CORES = 12  # Χρήση 12 πυρήνων του i9
EMBED_THREADS = 10  # Παράλληλα embeddings
BATCH_SIZE = 100    # Batch εγγραφή στη βάση

# Ορισμός των 4 πηγών/συλλογών
COLLECTIONS_CONFIG = {
    "AuthorizedThe": {"path": os.path.join(BASE_PATH, "AuthorizedThe"), "desc": "Εγκεκριμένα Θεωρητικά"},
    "AuthorizedMath": {"path": os.path.join(BASE_PATH, "AuthorizedMath"), "desc": "Εγκεκριμένα Μαθηματικά/Κώδικας"},
    "OneTimeThe": {"path": os.path.join(BASE_PATH, "OneTimeThe"), "desc": "Extra Θεωρητικά (OneTime)"},
    "OneTimeMath": {"path": os.path.join(BASE_PATH, "OneTimeMath"), "desc": "Extra Μαθηματικά/Κώδικας (OneTime)"}
}

# Φίμωμα των PDF warnings
logging.getLogger("pypdf").setLevel(logging.ERROR)

BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

def arrow_select(prompt, options):
    """Μενού επιλογής με βέλη πληκτρολογίου. Επιστρέφει το index της επιλογής."""
    result = [0]

    def _menu(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Πράσινο σε default background
        selected = 0
        n = len(options)

        while True:
            stdscr.clear()
            stdscr.addstr(0, 0, prompt, curses.A_BOLD)
            for i, opt in enumerate(options):
                if i == selected:
                    stdscr.addstr(i + 1, 0, f"  \u25b6 {opt}", curses.color_pair(1) | curses.A_BOLD)
                else:
                    stdscr.addstr(i + 1, 0, f"    {opt}")
            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord('k')):
                selected = (selected - 1) % n
            elif key in (curses.KEY_DOWN, ord('j')):
                selected = (selected + 1) % n
            elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                result[0] = selected
                return

    curses.wrapper(_menu)
    print(f"{prompt}")
    print(f"  {GREEN}▶ {BOLD}{options[result[0]]}{RESET}\n")
    return result[0]

def get_embedding(text):
    try:
        response = requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
        return response.json().get("embedding") if response.status_code == 200 else None
    except: return None

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    code_extensions = [".txt", ".py", ".cs", ".java", ".js", ".ts", ".html", ".css", ".json", ".sql"]
    try:
        if ext in code_extensions:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                text = f"--- ΑΡΧΕΙΟ: {os.path.basename(file_path)} ---\n" + text
        elif ext == ".pdf":
            reader = PdfReader(file_path)
            for page in reader.pages: text += page.extract_text() + "\n"
            if len(text.strip()) < 50:
                for img in convert_from_path(file_path): text += pytesseract.image_to_string(img, lang='ell+eng')
    except: pass
    return (file_path, text)

def index_collection(col_name, folder_path, client):
    collection = client.get_or_create_collection(col_name)
    files = glob.glob(os.path.join(folder_path, "*"))
    files = [f for f in files if os.path.isfile(f)]
    total_files = len(files)

    if total_files == 0:
        print(f"ℹ️  Ο φάκελος '{col_name}' είναι άδειος. Παράκαμψη.")
        return

    print(f"\n📂 {BOLD}Έναρξη Indexing για τη συλλογή: {col_name}{RESET}")
    print(f"📄 Αρχεία: {BOLD}{total_files}{RESET}")

    with ProcessPoolExecutor(max_workers=PARSING_CORES) as executor:
        results = list(tqdm(executor.map(extract_text, files), total=total_files, desc=f"📖 Reading {col_name}"))

    all_chunks = []
    for f, content in results:
        if not content.strip(): continue
        chunks = [content[i:i+800] for i in range(0, len(content), 700)]
        for i, chunk in enumerate(chunks): all_chunks.append((f, i, chunk))

    total_chunks = len(all_chunks)
    if total_chunks == 0: return

    def process_embedding(task):
        f, idx, chunk = task
        emb = get_embedding(chunk)
        return (chunk, emb, f"{col_name}_{os.path.basename(f)}_{idx}") if emb else None

    with ThreadPoolExecutor(max_workers=EMBED_THREADS) as executor:
        emb_results = list(tqdm(executor.map(process_embedding, all_chunks), total=total_chunks, desc="⚡ Vectorizing"))

    valid_data = [res for res in emb_results if res is not None]

    for i in range(0, len(valid_data), BATCH_SIZE):
        batch = valid_data[i : i + BATCH_SIZE]
        collection.add(
            documents=[b[0] for b in batch],
            embeddings=[b[1] for b in batch],
            ids=[b[2] for b in batch]
        )
    print(f"✅ Η συλλογή {col_name} ενημερώθηκε με {len(valid_data)} vectors.")

# ── Σταθερές για το Wikipedia pipeline ─────────────────────────────────────
WIKI_PARSE_CORES  = 12   # ProcessPool για clean_wikitext (CPU-bound, i9-14900HX)
WIKI_EMBED_THREADS = 16  # ThreadPool για embeddings (I/O-bound προς Ollama)
WIKI_READ_QUEUE   = 500  # max raw articles στη μνήμη ταυτόχρονα
WIKI_CHUNK_QUEUE  = 2000 # max chunks έτοιμα για embedding


def clean_wikitext(raw: str) -> str:
    """Αφαιρεί wiki markup. Τρέχει σε ProcessPool (CPU-bound)."""
    if HAS_MWPARSER:
        try:
            parsed = mwparserfromhell.parse(raw)
            text = parsed.strip_code(normalize=True, collapse=True)
        except Exception:
            text = raw
    else:
        text = re.sub(r"\{\{.*?\}\}", "", raw, flags=re.DOTALL)
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
        text = re.sub(r"\[https?://[^\s\]]+ ([^\]]+)\]", r"\1", text)
        text = re.sub(r"={2,}(.+?)={2,}", r"\1", text)
        text = re.sub(r"'{2,}", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [l for l in text.splitlines()
             if not l.strip().startswith(("[[Κατηγορία:", "[[Category:", "|", "!|", "{|"))]
    return "\n".join(lines).strip()


def _clean_and_chunk(args):
    """
    Εκτελείται σε ProcessPool worker.
    Δέχεται (title, raw) → επιστρέφει list[(doc_id, chunk_text)] ή [].
    """
    title, raw = args
    clean = clean_wikitext(raw)
    if len(clean) < 200:
        return []
    safe = re.sub(r"[^a-zA-Z0-9_\u0370-\u03FF\u1F00-\u1FFF-]", "_", title)
    return [
        (f"wiki_{safe[:60]}_{i}", f"[{title}]\n{chunk}")
        for i, chunk in enumerate(clean[j:j+800] for j in range(0, len(clean), 700))
    ]


def _bz2_reader(dump_path: str, raw_q, limit: int):
    """
    Thread: διαβάζει το bz2 streaming και βάζει (title, raw) στην raw_q.
    Τελειώνει βάζοντας None sentinel.
    """
    import queue as _q
    NS_ARTICLE = "0"
    xml_ns = ""

    with bz2.open(dump_path, "rb") as f:
        for event, elem in ET.iterparse(f, events=("start",)):
            if elem.tag.startswith("{"):
                xml_ns = elem.tag.split("}")[0] + "}"
            break

    count = 0
    title = ns = None
    with bz2.open(dump_path, "rb") as f:
        for event, elem in ET.iterparse(f, events=("end",)):
            local = elem.tag.replace(xml_ns, "")
            if local == "title":
                title = elem.text or ""
            elif local == "ns":
                ns = elem.text or ""
            elif local == "text":
                if ns == NS_ARTICLE and title and elem.text:
                    raw = elem.text
                    if not raw.strip().lower().startswith("#redirect"):
                        raw_q.put((title, raw))
                        count += 1
                        if limit and count >= limit:
                            elem.clear()
                            break
                elem.clear()
            elif local == "page":
                title = ns = None
                elem.clear()
    raw_q.put(None)  # sentinel


def index_wikipedia_dump(dump_path: str, collection_name: str = "AuthorizedThe", limit: int = 0):
    """
    Πλήρως παράλληλο pipeline για Wikipedia dump (.xml.bz2):

      [bz2 reader thread]
           ↓  raw_queue
      [ProcessPool x12  — clean_wikitext + chunking]
           ↓  chunk_queue
      [ThreadPool  x16  — embeddings → Ollama]
           ↓
      [ChromaDB batch writer]

    Όλα τρέχουν ταυτόχρονα. Η μνήμη ελέγχεται με bounded queues.
    """
    import threading
    import queue

    if not os.path.exists(dump_path):
        print(f"{YELLOW}⚠️  Δεν βρέθηκε το αρχείο: {dump_path}{RESET}")
        return

    if not HAS_MWPARSER:
        print(f"{YELLOW}⚠️  mwparserfromhell δεν βρέθηκε — χρήση regex fallback.")
        print(f"   pip install mwparserfromhell{RESET}")

    client     = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(collection_name)

    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"🌐 {BOLD}Wikipedia Dump Indexer  —  Πλήρως Παράλληλο Pipeline{RESET}")
    print(f"   Αρχείο     : {dump_path}")
    print(f"   Συλλογή    : {BOLD}{collection_name}{RESET}")
    print(f"   Όριο       : {'Χωρίς όριο' if not limit else f'{limit:,} άρθρα'}")
    print(f"   Cleaner    : {BOLD}{WIKI_PARSE_CORES} processes{RESET}  {'(mwparserfromhell)' if HAS_MWPARSER else '(regex fallback)'}")
    print(f"   Embedder   : {BOLD}{WIKI_EMBED_THREADS} threads{RESET}  →  Ollama/{EMBED_MODEL}")
    print(f"{CYAN}{'='*60}{RESET}\n")

    # ── Queues ───────────────────────────────────────────────────────────────
    raw_q   = queue.Queue(maxsize=WIKI_READ_QUEUE)   # (title, raw_wikitext)
    chunk_q = queue.Queue(maxsize=WIKI_CHUNK_QUEUE)  # (doc_id, chunk_text)

    # ── Counters (thread-safe) ───────────────────────────────────────────────
    lock          = threading.Lock()
    articles_read = [0]
    chunks_made   = [0]
    vecs_ok       = [0]
    vecs_skip     = [0]

    # ── Progress bars ────────────────────────────────────────────────────────
    bar_read  = tqdm(desc="  📄 Ανάγνωση  άρθρων ", unit=" άρθρο", dynamic_ncols=True, colour="cyan",   position=0)
    bar_clean = tqdm(desc="  🧹 Cleaning+Chunking", unit=" chunk",  dynamic_ncols=True, colour="yellow", position=1)
    bar_embed = tqdm(desc="  ⚡ Vectorizing       ", unit=" chunk",  dynamic_ncols=True, colour="green",  position=2)

    # ════════════════════════════════════════════════════════════════════════
    # STAGE 1 — bz2 reader  (1 thread, I/O-bound)
    # ════════════════════════════════════════════════════════════════════════
    def reader_worker():
        _bz2_reader(dump_path, raw_q, limit)

    reader_thread = threading.Thread(target=reader_worker, daemon=True)
    reader_thread.start()

    # ════════════════════════════════════════════════════════════════════════
    # STAGE 2 — clean + chunk  (ProcessPool, CPU-bound)
    # ════════════════════════════════════════════════════════════════════════
    def cleaner_worker():
        """Drains raw_q, submits to ProcessPool, pushes chunks to chunk_q."""
        batch_size = WIKI_PARSE_CORES * 4   # Feed the pool in batches
        with ProcessPoolExecutor(max_workers=WIKI_PARSE_CORES) as pool:
            pending = []
            done = False
            while not done:
                # Γέμισε batch
                while len(pending) < batch_size:
                    item = raw_q.get()
                    if item is None:
                        done = True
                        break
                    pending.append(item)
                    with lock:
                        articles_read[0] += 1
                    bar_read.update(1)

                if not pending:
                    break

                # Παράλληλο clean+chunk
                for result in pool.map(_clean_and_chunk, pending):
                    for chunk_tuple in result:
                        chunk_q.put(chunk_tuple)
                        with lock:
                            chunks_made[0] += 1
                        bar_clean.update(1)
                pending = []

        chunk_q.put(None)  # sentinel για embedder

    cleaner_thread = threading.Thread(target=cleaner_worker, daemon=True)
    cleaner_thread.start()

    # ════════════════════════════════════════════════════════════════════════
    # STAGE 3 — embed + write  (ThreadPool, I/O-bound προς Ollama)
    # ════════════════════════════════════════════════════════════════════════
    def embed_and_write():
        write_lock  = threading.Lock()
        batch_docs  = []
        batch_embs  = []
        batch_ids   = []

        def flush_batch():
            if batch_docs:
                with write_lock:
                    collection.add(
                        documents=batch_docs[:],
                        embeddings=batch_embs[:],
                        ids=batch_ids[:]
                    )
                batch_docs.clear()
                batch_embs.clear()
                batch_ids.clear()

        def embed_one(task):
            doc_id, text = task
            emb = get_embedding(text)
            return (doc_id, text, emb)

        with ThreadPoolExecutor(max_workers=WIKI_EMBED_THREADS) as pool:
            # Drain chunk_q σε rolling batches για το ThreadPool
            work_batch = []
            sentinel_seen = False

            while not sentinel_seen:
                # Μάζεψε ένα batch από το chunk_q
                while len(work_batch) < BATCH_SIZE * 2:
                    item = chunk_q.get()
                    if item is None:
                        sentinel_seen = True
                        break
                    work_batch.append(item)

                if not work_batch:
                    break

                for result in pool.map(embed_one, work_batch):
                    doc_id, text, emb = result
                    bar_embed.update(1)
                    if emb is None:
                        with lock: vecs_skip[0] += 1
                        continue
                    batch_docs.append(text)
                    batch_embs.append(emb)
                    batch_ids.append(doc_id)
                    with lock: vecs_ok[0] += 1

                    if len(batch_docs) >= BATCH_SIZE:
                        flush_batch()

                    bar_embed.set_postfix({
                        "indexed": f"{vecs_ok[0]:,}",
                        "skip": vecs_skip[0]
                    })
                work_batch = []

            flush_batch()  # τελευταίο batch

    embed_and_write()   # τρέχει στο main thread ενώ τα άλλα stages είναι daemons

    # Περίμενε να τελειώσουν
    reader_thread.join()
    cleaner_thread.join()

    bar_read.close()
    bar_clean.close()
    bar_embed.close()

    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"✅ {BOLD}Wikipedia indexing ολοκληρώθηκε!{RESET}")
    print(f"   Άρθρα διαβάστηκαν : {articles_read[0]:,}")
    print(f"   Chunks δημιουργήθηκαν: {chunks_made[0]:,}")
    print(f"   Vectors αποθηκεύτηκαν: {GREEN}{vecs_ok[0]:,}{RESET}")
    print(f"   Παραλείφθηκαν        : {YELLOW}{vecs_skip[0]:,}{RESET}")
    print(f"   Συλλογή              : {BOLD}{collection_name}{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")


def index_all_materials():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    print(f"\n{CYAN}{'='*50}{RESET}")
    print(f"🚀 {BOLD}Καθολικό Indexing Συλλογών RAG{RESET}")
    print(f"{CYAN}{'='*50}{RESET}")

    for col_name, config in COLLECTIONS_CONFIG.items():
        if not os.path.exists(config["path"]):
            os.makedirs(config["path"], exist_ok=True)
            print(f"📁 Δημιουργήθηκε ο φάκελος: {config['path']}")
        index_collection(col_name, config["path"], client)

    print(f"\n{GREEN}✨ Όλες οι συλλογές συγχρονίστηκαν επιτυχώς!{RESET}\n")

def query_single_collection(collection_name, embedding, client):
    try:
        collection = client.get_collection(collection_name)
        results = collection.query(query_embeddings=[embedding], n_results=3)
        return results["documents"][0] if results and results["documents"] else []
    except:
        return []

def query_rag_stream(question, model_name, mode, include_onetime):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    emb = get_embedding(question)
    if not emb: return print("❌ Σφάλμα: Αποτυχία λήψης embedding.")

    collections_to_query = []

    if mode == "generic":
        collections_to_query.append("AuthorizedThe")
        collections_to_query.append("AuthorizedMath")
        if include_onetime:
            collections_to_query.extend(["OneTimeThe", "OneTimeMath"])
    elif mode == "the":
        collections_to_query.append("AuthorizedThe")
        if include_onetime:
            collections_to_query.append("OneTimeThe")
    elif mode == "math":
        collections_to_query.append("AuthorizedMath")
        if include_onetime:
            collections_to_query.append("OneTimeMath")

    context_list = []
    with ThreadPoolExecutor(max_workers=len(collections_to_query)) as executor:
        futures = {executor.submit(query_single_collection, col, emb, client): col for col in collections_to_query}
        for future in futures:
            context_list.extend(future.result())

    context = "\n--- Νέο Τμήμα Υλικού ---\n".join(context_list) if context_list else "Δεν βρέθηκε σχετικό υποστηρικτικό υλικό."
    prompt = f"Χρησιμοποίησε το παρακάτω υλικό για να απαντήσεις στην ερώτηση.\n\nΥλικό:\n{context} \n\nΕρώτηση: {question}\nΑπάντηση:"

    print(f"\n🤖 {BOLD}{model_name}{RESET} [{mode.upper()} - Extra Sources: {include_onetime}]: ", end="", flush=True)

    full_response = ""
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate",
                                 json={"model": model_name, "prompt": prompt, "stream": True},
                                 stream=True, timeout=120)

        for line in response.iter_lines():
            if line:
                json_response = json.loads(line)
                chunk = json_response.get("response", "")
                full_response += chunk

                chunk = chunk.replace("\\geq", " >= ").replace("\\leq", " <= ").replace("\\times", " * ")
                if "<think>" in chunk: chunk = chunk.replace("<think>", "\n\n--- 🧠 Σκέψη ---\n")
                if "</think>" in chunk: chunk = chunk.replace("</think>", "\n\n--- 📝 Απάντηση ---\n")

                print(chunk, end="", flush=True)
        print("\n")

        # --- ΑΥΤΟΜΑΤΟΣ ΜΗΧΑΝΙΣΜΟΣ ΕΞΑΓΩΓΗΣ ΑΡΧΕΙΩΝ ---
        # ΔΙΟΡΘΩΣΗ: Το αρχικό pattern είχε literal newline μέσα στο string αντί για \n
        code_blocks = re.findall(r"```([a-zA-Z0-9+#-]+)\n(.*?)```", full_response, re.DOTALL)

        if code_blocks:
            print(f"{YELLOW}═" * 50)
            print(f"📦 Εντοπίστηκαν {len(code_blocks)} μπλοκ κώδικα στην απάντηση!")
            print(f"{YELLOW}═" * 50 + f"{RESET}")

            os.makedirs(OUTPUT_PATH, exist_ok=True)

            for idx, (lang, code_content) in enumerate(code_blocks):
                extensions = {
                    "python": "py", "py": "py", "csharp": "cs", "cs": "cs",
                    "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
                    "html": "html", "css": "css", "java": "java", "sql": "sql", "json": "json"
                }
                ext = extensions.get(lang.lower(), "txt")

                print(f"[{idx + 1}] Βρέθηκε κώδικας τύπου: {BOLD}{lang.upper()}{RESET}")
                save_opt = input("💾 Θέλεις να εξαχθεί σε αρχείο στο Output; (y/n): ").strip().lower()

                if save_opt == 'y':
                    filename = input(f"📝 Δώσε όνομα αρχείου (χωρίς κατάληξη): ").strip()
                    if not filename:
                        filename = f"generated_code_{idx + 1}"

                    full_filename = os.path.join(OUTPUT_PATH, f"{filename}.{ext}")
                    with open(full_filename, "w", encoding="utf-8") as f:
                        f.write(code_content.strip())

                    print(f"✅ {GREEN}Αποθηκεύτηκε στο: {full_filename}{RESET}\n")

    except Exception as e:
        print(f"\n❌ Σφάλμα επικοινωνίας: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Όνομα μοντέλου Ollama", default=None)
    args = parser.parse_args()

    model_name = args.model if args.model else input("🤖 Επίλεξε Μοντέλο (π.χ. qwen2.5-coder:7b): ").strip()
    if not model_name: model_name = "qwen2.5-coder:7b"

    mode_idx = arrow_select(
        f"{BOLD}Διαθέσιμα Modes Λειτουργίας:{RESET}",
        [
            "Generic      (Αναζήτηση σε Θεωρία + Μαθηματικά/Κώδικα)",
            "Theoretical  (Αναζήτηση μόνο στα Θεωρητικά)",
            "Coder        (Αναζήτηση μόνο στα Μαθηματικά/Κώδικα)",
        ]
    )
    mode = ["generic", "the", "math"][mode_idx]

    onetime_idx = arrow_select(
        "🔍 Συμπερίληψη Extra (OneTime) πηγών;",
        ["Ναι", "Όχι"]
    )
    include_onetime = onetime_idx == 0

    for config in COLLECTIONS_CONFIG.values():
        os.makedirs(config["path"], exist_ok=True)
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    if not os.path.exists(CHROMA_PATH):
        print(f"\n⚠️  Δεν βρέθηκε βάση δεδομένων Vector DB. Έναρξη πρώτης αρχειοθέτησης...")
        index_all_materials()

    mode_labels = {
        "generic": "Θεωρία + Μαθηματικά/Κώδικας",
        "the":     "Θεωρητικά",
        "math":    "Μαθηματικά / Κώδικας",
    }
    onetime_label = f"{GREEN}✔ Ενεργές{RESET}" if include_onetime else f"{YELLOW}✘ Ανενεργές{RESET}"

    print(f"\n{GREEN}🔥 Το σύστημα είναι έτοιμο. Πληκτρολόγησε την ερώτησή σου.{RESET}")
    print(f"💡 Γράψε {BOLD}'index'{RESET} για επανασυγχρονισμό των φακέλων, "
          f"{BOLD}'wiki'{RESET} για Wikipedia import ή {BOLD}'exit'{RESET} για έξοδο.")
    print(f"📌 Εστίαση: {BOLD}{CYAN}{mode_labels[mode]}{RESET}  |  Extra (OneTime) πηγές: {onetime_label}")

    while True:
        q = input(f"\n💬 {BOLD}Ερώτηση{RESET}: ").strip()
        if q.lower() == "exit":
            break
        elif q.lower() == "index":
            index_all_materials()
        elif q.lower() == "wiki":
            dump_path = input("📂 Path στο .xml.bz2 dump: ").strip()
            col_idx = arrow_select(
                "📚 Σε ποια συλλογή να αποθηκευτεί;",
                ["AuthorizedThe  (Κύρια θεωρητική βάση)", "OneTimeThe  (Extra / OneTime)"]
            )
            col_name = ["AuthorizedThe", "OneTimeThe"][col_idx]
            limit_str = input("🔢 Όριο άρθρων (Enter = όλα): ").strip()
            limit = int(limit_str) if limit_str.isdigit() else 0
            index_wikipedia_dump(dump_path, col_name, limit)
        elif q:
            query_rag_stream(q, model_name, mode, include_onetime)
