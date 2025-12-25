import os
import json
import re
import PyPDF2

# DIRECTORIES
UPLOAD_DIR = 'uploads'
TESTS_DIR = 'tests'
MANIFEST_FILE = 'tests/test_manifest.json'

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"❌ Error reading {pdf_path}: {e}")
    return text

def parse_forum_ias(text):
    questions = []
    
    # Split by "Q.<number>)" or "Q.<number>."
    # The regex looks for a newline followed by Q, dot/space, digits, then ) or .
    blocks = re.split(r'\nQ\.\s*\d+[\)\.]', text)
    
    # Skip the first split if it's junk (usually header text before Q1)
    if len(blocks) > 0:
        blocks = blocks[1:]

    for idx, block in enumerate(blocks):
        try:
            # 1. CLEANUP
            block = block.strip()
            
            # 2. EXTRACT ANSWER
            # Pattern: matches "Ans) c" or "Ans) C" or "Answer: c"
            ans_match = re.search(r'(?:Ans|Answer)[\)\:]\s*([a-dA-D])', block)
            correct_char = ans_match.group(1).lower() if ans_match else None
            
            # Map 'a'->0, 'b'->1 etc.
            ans_map = {'a': 0, 'b': 1, 'c': 2, 'd': 3}
            correct_idx = ans_map.get(correct_char, -1)

            # 3. EXTRACT METADATA (Subject/Topic)
            # Pattern in PDF: "Subject:) Polity"
            subj_match = re.search(r'Subject:\)\s*(.*)', block)
            subject = subj_match.group(1).strip() if subj_match else "General"

            # Pattern in PDF: "Topic:) ... "
            topic_match = re.search(r'Topic:\)\s*(.*)', block)
            topic = topic_match.group(1).strip() if topic_match else "GS"

            # 4. EXTRACT EXPLANATION
            # Usually starts with "Exp)" or "Explanation" and goes to end or next metadata
            exp_match = re.search(r'(?:Exp|Explanation)[\)\:]\s*(.*)', block, re.DOTALL | re.IGNORECASE)
            explanation = exp_match.group(1).strip() if exp_match else "No explanation found."

            # Remove Metadata lines from explanation if they got caught
            explanation = re.sub(r'(Subject:\)|Topic:\)|Source:\)).*', '', explanation, flags=re.DOTALL).strip()

            # 5. EXTRACT QUESTION TEXT & OPTIONS
            # Everything before "a)" is usually Question Text
            # We split by options a), b), c), d)
            
            # A rough splitter for options. 
            # Note: Forum IAS options are usually "a) ... b) ... "
            # We look for the options block start
            opt_start = re.search(r'\n\s*a[\)\.]', block)
            
            q_text = ""
            options = []
            
            if opt_start:
                q_text = block[:opt_start.start()].strip()
                
                # Extract options string
                # We limit the search area to before the Answer/Explanation starts
                end_of_opts = ans_match.start() if ans_match else len(block)
                opts_block = block[opt_start.start():end_of_opts]
                
                # Regex to grab a)... b)... c)... d)...
                # This is tricky because options might span lines.
                # We simply find the start of a), b), c), d) and slice.
                opt_matches = list(re.finditer(r'(?:^|\n)\s*([a-dA-D])[\)\.]', opts_block))
                
                for i in range(len(opt_matches)):
                    start = opt_matches[i].end()
                    end = opt_matches[i+1].start() if i + 1 < len(opt_matches) else len(opts_block)
                    options.append(opts_block[start:end].strip())
            else:
                q_text = "Error parsing question text."
                options = ["Parse Error", "Parse Error", "Parse Error", "Parse Error"]

            # 6. BUILD OBJECT
            q_obj = {
                "id": idx + 1,
                "text": q_text,
                "options": options,
                "correctAnswer": correct_idx,
                "explanation": explanation,
                "subject": subject,
                "topic": topic
            }
            questions.append(q_obj)

        except Exception as e:
            print(f"Error parsing Q{idx+1}: {e}")

    return questions

def update_manifest(filename, test_name):
    manifest = []
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, 'r') as f:
                manifest = json.load(f)
        except:
            manifest = []

    # Check if exists, update if so
    found = False
    for entry in manifest:
        if entry['filename'] == filename:
            entry['name'] = test_name
            found = True
            break
    
    if not found:
        manifest.append({"name": test_name, "filename": filename})

    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2)

def main():
    if not os.path.exists(UPLOAD_DIR):
        print(f"Directory {UPLOAD_DIR} missing. Creating...")
        os.makedirs(UPLOAD_DIR)
        return

    if not os.path.exists(TESTS_DIR):
        os.makedirs(TESTS_DIR)

    for f in os.listdir(UPLOAD_DIR):
        if f.endswith('.pdf'):
            print(f"Processing {f}...")
            text = extract_text_from_pdf(os.path.join(UPLOAD_DIR, f))
            questions = parse_forum_ias(text)
            
            if questions:
                out_name = f.replace('.pdf', '.json')
                with open(os.path.join(TESTS_DIR, out_name), 'w') as out_f:
                    json.dump(questions, out_f, indent=2)
                
                update_manifest(out_name, f.replace('.pdf', '').replace('-', ' '))
                print(f"✅ Generated {out_name} with {len(questions)} questions.")
                
                # Clean up upload so it doesn't re-process
                os.remove(os.path.join(UPLOAD_DIR, f))

if __name__ == "__main__":
    main()
