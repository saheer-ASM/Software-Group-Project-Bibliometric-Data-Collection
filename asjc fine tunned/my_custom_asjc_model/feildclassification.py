import os
import psycopg2
import torch
from dotenv import load_dotenv
from transformers import pipeline, TextClassificationPipeline

# Load environment variables from the parent folder's .env file
load_dotenv()

# ---------------- CUSTOM PIPELINE ----------------
class ASJCMultiLabelPipeline(TextClassificationPipeline):
    """Custom pipeline to return all sorted predictions (ignoring threshold)."""
    def postprocess(self, model_outputs, **kwargs):
        # FIX 1: Removed the extra torch.tensor() wrapper to fix the UserWarning
        scores = torch.sigmoid(model_outputs["logits"]).tolist()
        
        results = []
        for i, score in enumerate(scores[0]):
            # REMOVED the threshold check. We now grab every single field and score.
            label = self.model.config.id2label[i]
            results.append({"label": label, "score": float(score)})
        
        # Sort by descending score so the top fields are always first
        return sorted(results, key=lambda x: x["score"], reverse=True)


# ---------------- DB CONNECTION ----------------
def get_conn():
    """Create and return a connection to the PostgreSQL database"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT") or 5432),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )


# ---------------- MAIN SCRIPT ----------------
def main():
    print("========================================")
    print(" LOADING MODEL...")
    print("========================================")
    
    # Using the exact subfolder path as requested
    model_path = "./my_custom_asjc_model"
    pipe = pipeline(
        task="text-classification",
        model=model_path,
        tokenizer=model_path,
        pipeline_class=ASJCMultiLabelPipeline
    )
    print("Model loaded successfully!\n")

    conn = get_conn()
    cur = conn.cursor()

    # Fetch ALL unclassified publications
    print("Fetching ALL unclassified publications from DB...")
    cur.execute("""
        SELECT p.pub_id, p.pub_title, p.abstract 
        FROM publication p
        LEFT JOIN field_classification fc ON p.pub_id = fc.pub_id
        WHERE fc.pub_id IS NULL;
    """)
    publications = cur.fetchall()
    total_pubs = len(publications)

    if not publications:
        print("No unclassified publications found. Exiting.")
        cur.close()
        conn.close()
        return

    print(f"Found {total_pubs} publications to process.")

    # Process each publication
    for idx, (pub_id, title, abstract) in enumerate(publications, 1):
        print(f"\n[{idx}/{total_pubs}] Processing {pub_id}...")
        
        # Clean null values just in case
        safe_title = title if title else ""
        safe_abstract = abstract if abstract else ""
        
        # Format text exactly how the model expects it
        input_text = f"title={{{safe_title}}}, abstract={{{safe_abstract}}}"
        
        # Run inference (Added truncation to prevent the 512+ token limit crash!)
        raw_predictions = pipe(input_text, truncation=True, max_length=512)
        
        # FIX 2: Safely unwrap the predictions in case Hugging Face added an extra batch list
        if raw_predictions and isinstance(raw_predictions[0], list):
            predictions = raw_predictions[0]
        else:
            predictions = raw_predictions
        
        # Extract Top 3 predictions (This will now ALWAYS contain exactly 3 items)
        top_3 = predictions[:3]
        
        # Initialize default empty values for database insertion
        fields = [None, None, None]
        weights = [None, None, None]
        
        # 1. Calculate the total sum of the raw top 3 scores
        total_score = sum(pred['score'] for pred in top_3)
        
        # 2. Normalize each score so the top 3 combine to exactly 100%
        for i, pred in enumerate(top_3):
            fields[i] = pred['label']
            if total_score > 0:
                # Divides the score by the total and multiplies by 100 for percentages
                weights[i] = round((pred['score'] / total_score) * 100, 2)
            else:
                weights[i] = 0.00
        
        # Print the normalized results to the terminal
        print(f"  -> 1: {fields[0]} ({weights[0]}%)")
        print(f"  -> 2: {fields[1]} ({weights[1]}%)")
        print(f"  -> 3: {fields[2]} ({weights[2]}%)")

        # Insert into database
        try:
            cur.execute("""
                INSERT INTO field_classification 
                (pub_id, field1_name, field1_weight, field2_name, field2_weight, field3_name, field3_weight)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pub_id) DO UPDATE SET
                    field1_name = EXCLUDED.field1_name,
                    field1_weight = EXCLUDED.field1_weight,
                    field2_name = EXCLUDED.field2_name,
                    field2_weight = EXCLUDED.field2_weight,
                    field3_name = EXCLUDED.field3_name,
                    field3_weight = EXCLUDED.field3_weight;
            """, (pub_id, fields[0], weights[0], fields[1], weights[1], fields[2], weights[2]))
            
            # Commit every 100 publications to save progress safely
            if idx % 100 == 0:
                conn.commit()
                print(f"  [💾 SAVED] Progress committed to database at {idx} records.")

        except Exception as e:
            print(f"  [ERROR] Database insertion failed for {pub_id}: {e}")
            conn.rollback()
            continue

    # Final commit for any remaining records
    conn.commit()

    print("\n========================================")
    print(f"✅ SUCCESS! {total_pubs} publications classified, normalized to 100%, and saved to DB.")
    print("========================================")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()