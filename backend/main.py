from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import models, schemas, database
import os
import easyocr
import face_recognition
import numpy as np  # Import numpy for array handling
from typing import Optional, List

app = FastAPI()

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

# Dependency to provide a database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_face_to_db(db, name, code, encoding, image_path):
    face = models.Face(name=name, code=code, picture=image_path)
    face.set_landmarks(encoding)  # Преобразуем список в JSON перед сохранением
    db.add(face)
    db.commit()
    db.refresh(face)
    return face

def extract_face_encoding(image_path):
    # Load image
    image = face_recognition.load_image_file(image_path)
    
    # Find face locations
    face_locations = face_recognition.face_locations(image)
    
    # Get encodings for the faces in the image
    face_encodings = face_recognition.face_encodings(image, face_locations)
    
    if not face_encodings:
        return None
    
    # Assuming we are interested in the first face found
    return face_encodings[0]

def calculate_similarity(encoding1, encoding2):
    # Convert lists to numpy arrays
    encoding1_np = np.array(encoding1)
    encoding2_np = np.array(encoding2)
    
    # Calculate similarity between two face encodings
    return face_recognition.face_distance([encoding1_np], encoding2_np)[0]

# Function to extract a code (like ID) from the image using EasyOCR
def get_code(image_path):
    reader = easyocr.Reader(['en'])
    results = reader.readtext(image_path)

    # Initialize a variable to store the code
    code = None

    # Loop through the results to find a numeric code
    for (bbox, text, prob) in results:
        # Check if the text is numeric
        if text.isdigit():  # Check if the text is all digits
            code = text
            break  # Exit the loop once we find the code

    return int(code) if code else None

@app.post("/api/find_similar")
async def find_similar(image: UploadFile = File(...), db: Session = Depends(get_db)):
    # Save the uploaded image
    media_path = "media"
    if not os.path.exists(media_path):
        os.makedirs(media_path)
    
    image_path = os.path.join(media_path, image.filename)
    with open(image_path, "wb") as buffer:
        buffer.write(await image.read())

    # Extracting face landmarks from the uploaded image
    uploaded_face_encoding = extract_face_encoding(image_path)
    if uploaded_face_encoding is None:
        raise HTTPException(status_code=400, detail="No face detected in the image")

    # Searching for similar faces in the database
    faces = db.query(models.Face).all()
    similar_faces = []

    for face in faces:
        # Extracting landmarks for faces from the database
        db_face_encoding = face_recognition.face_encodings(face_recognition.load_image_file(face.picture))[0]
        similarity = calculate_similarity(uploaded_face_encoding, db_face_encoding)
        
        if similarity < 0.6:  # Example threshold
            similar_faces.append({
                "id": face.id,
                "name": face.name,
                "code": face.code,
                "landmarks": face.landmarks,  # Handle binary data properly
                "picture": face.picture
            })

    if not similar_faces:
        return {"message": "No similar faces found"}

    return similar_faces  # Ensure that `as_dict` method exists or adapt as needed

# API endpoint to upload an image, extract face data, and save to the database
@app.post("/api/upload_user")
async def upload_image(image: UploadFile = File(...), db: Session = Depends(get_db)):
    # Save the uploaded image to a media folder
    media_path = "media"
    if not os.path.exists(media_path):
        os.makedirs(media_path)
    
    image_path = os.path.join(media_path, image.filename)
    with open(image_path, "wb") as buffer:
        buffer.write(await image.read())

    # Extract the code from the image
    code = get_code(image_path)
    if code is None:
        raise HTTPException(status_code=400, detail="Unable to extract code from the image or code is not a valid integer")

    # Check if the code is unique
    existing_face = db.query(models.Face).filter(models.Face.code == code).first()
    if existing_face:
        raise HTTPException(status_code=400, detail="Code already exists in the database")

    # Extract face encoding from the image
    face_encoding = extract_face_encoding(image_path)
    if face_encoding is None:
        raise HTTPException(status_code=400, detail="No face detected in the image")

    # Save the extracted data to the database
    face = save_face_to_db(db=db, name=image.filename, code=code, encoding=face_encoding.tolist(), image_path=image_path)

    # Return the saved face data
    return face

@app.get("/api/faces/code/")
async def get_faces_by_code(code: Optional[int] = None, db: Session = Depends(get_db)):
    if code is not None:
        face = db.query(models.Face).filter(models.Face.code == code).first()
        if face is None:
            raise HTTPException(status_code=404, detail="Face not found")
        return {
            "id": face.id,
            "name": face.name,
            "code": face.code,
            "landmarks": face.landmarks,  # Ensure proper handling of binary data
            "picture": face.picture
        }
    else:
        faces = db.query(models.Face).all()
        return [
            {
                "id": face.id,
                "name": face.name,
                "code": face.code,
                "landmarks": face.landmarks,  # Ensure proper handling of binary data
                "picture": face.picture
            }
            for face in faces
        ]