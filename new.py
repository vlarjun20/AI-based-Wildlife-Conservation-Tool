from flask import Flask, render_template, jsonify, request, Response
import cv2
from ultralytics import YOLO
import time

app = Flask(__name__)

# Load the YOLO model
model = YOLO('wild.pt')  # You can replace with your trained model if needed

# Sample data for logs and analysis
sample_logs = [
    { 'id': 1, 'date': '2025-02-24', 'detection_time': '10:00 AM', 'close_time': '10:05 AM' },
    { 'id': 2, 'date': '2025-02-25', 'detection_time': '11:00 AM', 'close_time': '11:10 AM' }
]

# Home route
@app.route('/')
def home():
    return render_template('Home.html')

# Footages page route
@app.route('/detectedvideo')
def detectedvideo():
    return render_template('detectedvideo.html')

# Logs page route
@app.route('/logs')
def logs():
    return render_template('LOG.html')

# Analysis page route
@app.route('/analysis')
def analysis():
    return render_template('Analysis.html')

# API to get logs data
@app.route('/api/logs')
def get_logs():
    return jsonify(sample_logs)

# Stream video from webcam and perform human detection using YOLO
def detect_humans():
    cap = cv2.VideoCapture(0)  # Use 0 for webcam, or provide a video file path
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Use YOLO model to detect objects
        results = model(frame)

        # Draw bounding boxes and labels on the frame
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                label = result.names[box.cls[0].item()]
                confidence = box.conf.item()

                # Only consider human detections (label = 'person')
                if label == 'person':
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f'{label} {confidence:.2f}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Encode the frame in JPEG format
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        # Yield the frame in a byte stream
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

# Route to stream video
@app.route('/video_feed')
def video_feed():
    return Response(detect_humans(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)
