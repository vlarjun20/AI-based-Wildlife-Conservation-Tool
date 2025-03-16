import os
from flask import Flask, render_template, request, jsonify, Response
import cv2
from pymongo import MongoClient
import datetime
import logging
from PIL import Image
import io
import ollama

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
try:
    client = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    db = client['wildlife_conservation']  
    log_collection = db['detection_logs']  
    client.server_info()  # Test connection
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

def process_frame(frame):
    """Send frame to LLaVA model via Ollama and return the response."""
    try:
        # Convert OpenCV frame to PIL Image
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        # Convert to bytes for Ollama
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='JPEG')
        img_bytes = img_bytes.getvalue()

        # Send image to LLaVA via Ollama
        response = ollama.chat(
            model='llava',  
            messages=[{"role": "user", "content": "What is in the video(the camera is a night vision camera so ignore the resolution)?", "images": [img_bytes]}]
        )

        return response['message']['content']
    except Exception as e:
        logger.error(f"Error processing frame with LLaVA: {e}")
        return "Error processing frame."


#home page
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/footages')
def footages():
    try:
        video_folder = os.path.join('static', 'footages')  
        videos = os.listdir(video_folder)  
        
        # Filter videos by date if a date is provided in the query string
        selected_date = request.args.get('date')
        if selected_date:
            # Convert the date to match video filename format (e.g., detection_2025-03-13.mp4)
            videos = [video for video in videos if selected_date in video]
        
        return render_template('footages.html', videos=videos)
    except Exception as e:
        logger.error(f"Error fetching footages: {e}")
        return jsonify({"error": "Failed to fetch footages."}), 500


# Logs page route
@app.route('/logs')
def logs():
    return render_template('LOG.html')


# Analysis page route
@app.route('/analysis')
def analysis():
    return render_template('Analysis.html')


# API to get logs data from MongoDB
@app.route('/api/logs')
def get_logs():
    try:
        logs = log_collection.find()  # Fetch all logs from MongoDB
        logs_list = []
        for log in logs:
            logs_list.append({
                'date': log['date'],
                'detection_time': log['detection_time'],
                'close_time': log['close_time'],
                'description': log.get('description', "No description available.")
            })
        return jsonify(logs_list)
    except Exception as e:
        logger.error(f"Error fetching logs from MongoDB: {e}")
        return jsonify({"error": "Failed to fetch logs."}), 500


@app.route('/api/detection_logs', methods=['GET'])
def detection_logs():
    try:
        logs = log_collection.find({}, {"_id": 0, "date": 1, "detection_time": 1})
        logs_list = []
        for log in logs:
            logs_list.append({
                'date': log['date'],
                'detection_time': log['detection_time']
            })
        return jsonify(logs_list)
    except Exception as e:
        logger.error(f"Error fetching detection logs: {e}")
        return jsonify({"error": "Failed to fetch detection logs."}), 500


def detect_objects():
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Failed to open webcam.")
            return

        description_logged = False
        start_time = None
        video_writer = None
        video_filename = None

        # Ensure the footages directory exists
        video_folder = os.path.join('static', 'footages')
        if not os.path.exists(video_folder):
            os.makedirs(video_folder)  # Create the directory if it doesn't exist

        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to grab frame.")
                break

            # Get description from the process_frame function
            description = process_frame(frame)
            logger.info(f"Detection Output: {description}")

         
            if "person" in description.lower() and not description_logged:
                start_time = datetime.datetime.now()
                detection_time = start_time.strftime('%H:%M:%S')
                date = start_time.strftime('%Y-%m-%d')

                # Log detection into MongoDB
                try:
                    log_collection.insert_one({
                        'date': date,
                        'detection_time': detection_time,
                        'close_time': None,
                        'description': description
                    })
                    description_logged = True

                    # # Set up video writer to save the footage
                    # video_filename = os.path.join(video_folder, f'detection_{date}_{detection_time}.mp4')
                    # fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec
                    # video_writer = cv2.VideoWriter(video_filename, fourcc, 20.0, (frame.shape[1], frame.shape[0]))

                    # if not video_writer.isOpened():
                    #     logger.error(f"Failed to open video writer for {video_filename}")
                    #     return

                    # logger.info(f"Started saving video to {video_filename}")
                except Exception as e:
                    logger.error(f"Error logging detection to MongoDB: {e}")

            # Write the current frame to the video file if recording
            if video_writer is not None:
                video_writer.write(frame)

            # Encode the frame in JPEG format to stream it
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                logger.error("Failed to encode frame.")
                break

            frame = buffer.tobytes()

            # Yield the frame in a byte stream
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

            # Reset logging flag and stop recording when detection session ends
            if description_logged:
                close_time = datetime.datetime.now().strftime('%H:%M:%S')
                try:
                    log_collection.update_one(
                        {'date': date, 'detection_time': detection_time, 'close_time': None},
                        {'$set': {'close_time': close_time}}
                    )
                    description_logged = False
                    video_writer.release()  
                    logger.info(f"Finished saving video: {video_filename}")
                except Exception as e:
                    logger.error(f"Error updating close time in MongoDB: {e}")

    except Exception as e:
        logger.error(f"Error in detect_objects: {e}")
    finally:
        cap.release()
        if video_writer is not None:
            video_writer.release()  



# Route to stream video
@app.route('/video_feed')
def video_feed():
    return Response(detect_objects(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(debug=True)



