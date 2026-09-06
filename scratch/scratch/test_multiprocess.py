import time
from concurrent.futures import ProcessPoolExecutor
import pymupdf

pdf_path = r'data/raw/gsi/landslide_inventory.pdf'

def process_page_range(start_page, end_page):
    doc = pymupdf.open(pdf_path)
    page_rows = []
    for p in range(start_page, end_page):
        tabs = doc[p].find_tables()
        if tabs and tabs.tables:
            for r in tabs[0].extract():
                page_rows.append((p + 1, r))
    doc.close()
    return page_rows

if __name__ == '__main__':
    t0 = time.time()
    doc = pymupdf.open(pdf_path)
    n_pages = len(doc)
    doc.close()
    
    num_workers = 8
    chunk_size = (n_pages + num_workers - 1) // num_workers
    ranges = [(i * chunk_size, min((i + 1) * chunk_size, n_pages)) for i in range(num_workers)]
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_page_range, r[0], r[1]) for r in ranges]
        results = [f.result() for f in futures]
    
    all_rows = [row for res in results for row in res]
    print(f"Multiprocessing extracted {len(all_rows)} rows from {n_pages} pages in {time.time() - t0:.2f} seconds!")
