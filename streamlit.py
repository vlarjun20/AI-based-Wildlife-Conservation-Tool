import streamlit as st
import cv2
import datetime
import logging
import io
import ollama
import plotly.express as px
from pymongo import MongoClient
from PIL import Image
import numpy as np
import pandas as pd
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure saved_videos directory exists
os.makedirs("saved_videos", exist_ok=True)

# MongoDB Setup
try:
    client = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    db = client['wildlife_conservation']
    log_collection = db['detection_logs']
    client.server_info()  # Test connection
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# Function to process frame using LLaVA
def process_frame(frame):
    """Send frame to LLaVA model via Ollama and return the response."""
    try:
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='JPEG')
        img_bytes = img_bytes.getvalue()

        response = ollama.chat(
            model='llava',
            messages=[{"role": "user", "content": "What is in the video(the camera is a night vision camera so ignore the resolution)?", "images": [img_bytes]}],
            options={"num_gpu": 1}
        )

        return response['message']['content']
    except Exception as e:
        logger.error(f"Error processing frame with LLaVA: {e}")
        return "Error processing frame."

# Streamlit UI
st.set_page_config(page_title="Wildlife Conservation", layout="wide")
st.title("🐾 Wildlife Conservation Monitoring System")

# Sidebar Navigation
menu = st.sidebar.radio("Navigation", ["Live Detection", "Logs", "Saved Footages", "Analysis", "Profile"])

# Live Detection Page
if menu == "Live Detection":
    st.subheader("📹 Real-Time Wildlife Detection")

    # Placeholder for the camera feed
    live_feed = st.image([])  

    cap = None

    if st.sidebar.button("Start Detection",key="start_btn"):
        cap = cv2.VideoCapture(0) 

        description_logged = False
        recording = False  
        video_writer = None  
        video_filename = None

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                st.error("Failed to grab frame.")
                break

            # Convert BGR (OpenCV default) to RGB for Streamlit display
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            live_feed.image(frame_rgb, channels="RGB")

            # Process frame with LLaVA
            description = process_frame(frame)
            logger.info(f"LLaVA Output: {description}")

            # Detecting people and start recording
            if "person" in description.lower() or "people" in description.lower():
                if not description_logged:
                    video_folder = "saved_videos"
                    os.makedirs(video_folder, exist_ok=True)
                    start_time = datetime.datetime.now()
                    detection_time = start_time.strftime('%H:%M:%S')
                    date = start_time.strftime('%Y-%m-%d')
                    timestamp = start_time.strftime('%Y-%m-%d_%H-%M-%S')

                    video_filename = f"saved_videos/footage_{date}_{detection_time.replace(':', '-')}.mp4"
                    video_writer = cv2.VideoWriter(
                        video_filename,
                        cv2.VideoWriter_fourcc(*"mp4v"),  
                        (frame.shape[1], frame.shape[0])
                    )

                    recording = True
                    try:
                        log_entry = log_collection.insert_one({
                            'date': date,
                            'detection_time': detection_time,
                            'close_time': None,
                            'description': description,
                            'video_filename': video_filename
                        })
                        log_entry_id = log_entry.inserted_id  
                        description_logged = True
                        logger.info("Detection logged and recording started.")
                    except Exception as e:
                        logger.error(f"Error logging detection: {e}")

            else:
                # Stop recording when no people are detected
                if description_logged:
                    close_time = datetime.datetime.now().strftime('%H:%M:%S')
                    try:
                        log_collection.update_one(
                            {'_id': log_entry_id},
                            {'$set': {'close_time': close_time}}
                        )
                        logger.info("Close time updated in MongoDB.")
                        if recording and video_writer is not None:
                            video_writer.release()
                            recording = False
                            logger.info(f"Recording saved: {video_filename}")

                    except Exception as e:
                        logger.error(f"Error updating close time: {e}")

                description_logged = False  

            # Stop detection button
            if st.sidebar.button("Stop Detection",key="stop_btn"):
                cap.release()
                st.success("Detection Stopped.")
                break

        cap.release()
        live_feed.image([])  # Clear the stream

# Logs Page
elif menu == "Logs":
    st.subheader("📜 Detection Logs")
    logs = log_collection.find()
    logs_list = [[log['date'], log['detection_time'], log['close_time'], log.get('description', 'No description')] for log in logs]

    df = pd.DataFrame(logs_list, columns=["Date", "Start Time", "End Time", "Description"])
    
    if not df.empty:
        st.dataframe(df)
    else:
        st.warning("No logs found.")

# Saved Footages Page
elif menu == "Saved Footages":
    st.subheader("🎥 Saved Wildlife Footages")

    logs = log_collection.find({"video_filename": {"$exists": True}})
    videos = [log["video_filename"] for log in logs if "video_filename" in log]
    video_folder = "saved_videos"
    os.makedirs(video_folder, exist_ok=True)
    
    if not videos:
        st.warning("No saved footages found.")
    else:
        for video in videos:
            full_path = os.path.join(video_folder, os.path.basename(video)) 

            if os.path.exists(full_path): 
                st.write(f"📂 **Recorded Footage:** {full_path}")
                with open(full_path, "rb") as video_file:
                    video_bytes = video_file.read()
                    st.video(video_bytes)
                    st.download_button("Download Video", video_bytes, file_name=os.path.basename(video))
            else:
                st.error(f"⚠️ Video file not found: {full_path}")

# Analysis Page
elif menu == "Analysis":
    st.subheader("📊 Wildlife Detection Analysis")

    logs = log_collection.find()
    logs_list = [[log['date'], log.get('description', 'Unknown')] for log in logs]

    df = pd.DataFrame(logs_list, columns=["Date", "Description"])

    if df.empty:
        st.warning("No data available for analysis.")
    else:
        detection_counts = df.groupby("Date").size().reset_index(name="Detections")

        fig = px.bar(
            detection_counts, x="Date", y="Detections",
            text_auto=True, title="📈 Number of Detections Per Day",
            color="Detections",
            color_continuous_scale="turbo"
        )
        fig.update_layout(xaxis_title="Date", yaxis_title="Number of Detections", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        selected_date = st.selectbox("Select Date to View Detections", df["Date"].unique())
        if selected_date:
            filtered_df = df[df["Date"] == selected_date]
            st.write(f"**Detections on {selected_date}:**")
            for desc in filtered_df["Description"]:
                st.markdown(f"✅ {desc}")

# Profile Page
elif menu == "Profile":
    st.subheader("👮‍♂️ Forest Officer Profile")

    profile_collection = db["forest_officer"]
    existing_profile = profile_collection.find_one({}, {"_id": 0})

    if existing_profile:
        st.image(existing_profile.get("photo", "https://via.placeholder.com/150"), width=150)
        st.write(f"**Name:** {existing_profile['name']}")
        st.write(f"**Officer ID:** {existing_profile['officer_id']}")
        st.write(f"**Email:** {existing_profile['email']}")
        st.write(f"**Phone:** {existing_profile['phone']}")
        st.success("Profile loaded successfully.")
