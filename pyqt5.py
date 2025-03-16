import sys
import cv2
import datetime
import logging
import io
import ollama
from pymongo import MongoClient
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QTextBrowser
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
try:
    client = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=5000)
    db = client['wildlife_conservation']  
    log_collection = db['detection_logs']
    client.server_info()  
    logger.info("Connected to MongoDB successfully.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

class WildlifeMonitor(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Wildlife Conservation Monitor")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Layout
        self.layout = QVBoxLayout()

        # Video display label
        self.video_label = QLabel(self)
        self.layout.addWidget(self.video_label)

        # Logs Display
        self.logs_display = QTextBrowser()
        self.layout.addWidget(self.logs_display)

        # Buttons
        self.start_button = QPushButton("Start Detection")
        self.start_button.clicked.connect(self.start_detection)
        self.layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Detection")
        self.stop_button.clicked.connect(self.stop_detection)
        self.layout.addWidget(self.stop_button)

        self.refresh_logs_button = QPushButton("Refresh Logs")
        self.refresh_logs_button.clicked.connect(self.load_logs)
        self.layout.addWidget(self.refresh_logs_button)

        self.central_widget.setLayout(self.layout)

        # Video Capture
        self.cap = cv2.VideoCapture(0)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # State Variables
        self.description_logged = False
        self.start_time = None

    def process_frame(self, frame):
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
                messages=[{"role": "user", "content": "What is in the image?", "images": [img_bytes]}],
                options={"num_gpu": 1}
            )

            return response['message']['content']
        except Exception as e:
            logger.error(f"Error processing frame with LLaVA: {e}")
            return "Error processing frame."

    def update_frame(self):
        """Update the video feed and process frames."""
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to grab frame.")
            return
        
        # Get description from LLaVA
        description = self.process_frame(frame)
        logger.info(f"LLaVA Output: {description}")

        # Log Detection
        if not self.description_logged:
            self.start_time = datetime.datetime.now()
            detection_time = self.start_time.strftime('%H:%M:%S')
            date = self.start_time.strftime('%Y-%m-%d')

            try:
                log_collection.insert_one({
                    'date': date,
                    'detection_time': detection_time,
                    'close_time': None,
                    'description': description
                })
                self.description_logged = True
            except Exception as e:
                logger.error(f"Error logging detection to MongoDB: {e}")

        # Convert Frame to QPixmap
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_image))

        # Reset Logging
        if self.description_logged:
            close_time = datetime.datetime.now().strftime('%H:%M:%S')
            try:
                log_collection.update_one(
                    {'date': date, 'detection_time': detection_time, 'close_time': None},
                    {'$set': {'close_time': close_time}}
                )
                self.description_logged = False
            except Exception as e:
                logger.error(f"Error updating close time in MongoDB: {e}")

    def start_detection(self):
        """Start video capture and object detection."""
        self.cap.open(0)
        self.timer.start(50)

    def stop_detection(self):
        """Stop video capture and object detection."""
        self.timer.stop()
        self.cap.release()
        self.video_label.clear()

    def load_logs(self):
        """Load logs from MongoDB and display in text browser."""
        try:
            logs = log_collection.find()
            logs_text = ""
            for log in logs:
                logs_text += f"Date: {log['date']}, Start: {log['detection_time']}, End: {log['close_time']}, Description: {log.get('description', 'No description')}\n"
            self.logs_display.setText(logs_text)
        except Exception as e:
            logger.error(f"Error fetching logs from MongoDB: {e}")
            self.logs_display.setText("Failed to fetch logs.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WildlifeMonitor()
    window.show()
    sys.exit(app.exec_())
