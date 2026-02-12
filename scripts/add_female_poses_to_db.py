import os
import base64
import mysql.connector

# Update these with your DB credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Ldr1@#45",
    "database": "posea_db"
}

POSE_DIR = "app/static/Beach_Dataset/female"

# This script reads all images from the specified directory, encodes them in base64, and inserts them into the pose_library table in the database
def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    for filename in os.listdir(POSE_DIR):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            with open(os.path.join(POSE_DIR, filename), "rb") as img_file:
                b64 = base64.b64encode(img_file.read()).decode("utf-8")
                data_url = f"data:image/png;base64,{b64}"
                # Insert pose data into the database
                cursor.execute(
                    "INSERT INTO pose_library (pose_image_base64, gender, pose_image, description) VALUES (%s, %s, %s, %s)",
                    (data_url, "female", filename, f"Pose for {filename}")
                )
    conn.commit()
    cursor.close()
    conn.close()
    print("All female poses added to DB.")

if __name__ == "__main__":
    main()
