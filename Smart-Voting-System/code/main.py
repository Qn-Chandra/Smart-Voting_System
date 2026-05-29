from flask import Flask, render_template, url_for, request, session, flash, redirect
from flask_mail import *
from flask_socketio import SocketIO, emit
from email.mime.multipart import MIMEMultipart
import smtplib
import pymysql
import pandas as pd
import numpy as np
import os
import cv2
from PIL import Image
import shutil
import datetime
import time
import requests
import mediapipe as mp
import pyaudio
import wave
import speech_recognition as sr
import threading
import pyttsx3
import random


facedata = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
cascade = cv2.CascadeClassifier(facedata)

#import mediapipe as mp

# Mediapipe setup
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Liveness check function
def check_liveness(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    if results.multi_face_landmarks:
        landmarks = results.multi_face_landmarks[0].landmark
        left_eye_top = landmarks[159].y
        left_eye_bottom = landmarks[145].y
        right_eye_top = landmarks[386].y
        right_eye_bottom = landmarks[374].y
        left_ratio = abs(left_eye_top - left_eye_bottom)
        right_ratio = abs(right_eye_top - right_eye_bottom)
        avg_ratio = (left_ratio + right_ratio) / 2
        return True, avg_ratio, landmarks
    return False, 0, None

def speak_blink():
    """Random time পরে blink করতে বলবে"""
    wait_time = random.uniform(1, 7)  # ← 1-7 seconds random
    print(f"Will ask to blink after {wait_time:.1f} seconds")
    time.sleep(wait_time)
    tts_engine.say("Blink your eyes")
    tts_engine.runAndWait()
    print("Said: Blink your eyes!")


mydb=pymysql.connect(host='localhost', user='root', password='@chandra123', port=3306, database='smart_voting_system')

sender_address = 'mandalchandra204@gmail.com' #enter sender's email id
sender_pass = 'whoo bwvg lcft ozom' #enter sender's password

app=Flask(__name__)
app.config['SECRET_KEY']='ajsihh98rw3fyes8o3e9ey3w5dc'
socketio = SocketIO(app) 
# Audio monitoring global variables
audio_threat_detected = threading.Event()
# Text to speech engine setup
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150)    # speed
tts_engine.setProperty('volume', 1.0)  # volume


@app.before_first_request
def initialize():
    session['IsAdmin']=False
    session['User']=None

@app.route('/')
@app.route('/home')
def home():
    return render_template('index.html')

@app.route('/admin', methods=['POST','GET'])
def admin():
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        if (email=='admin@voting.com') and (password=='admin'):
            session['IsAdmin']=True
            session['User']='admin'
            flash('Admin login successful','success')
    return render_template('admin.html', admin=session['IsAdmin'])

@app.route('/add_nominee', methods=['POST','GET'])
def add_nominee():
    if request.method=='POST':
        member=request.form['member_name']
        party=request.form['party_name']
        logo=request.form['test']
        nominee=pd.read_sql_query('SELECT * FROM nominee', mydb)
        all_members=nominee.member_name.values
        all_parties=nominee.party_name.values
        all_symbols=nominee.symbol_name.values
        if member in all_members:
            flash(r'The member already exists', 'info')
        elif party in all_parties:
            flash(r"The party already exists", 'info')
        elif logo in all_symbols:
            flash(r"The logo is already taken", 'info')
        else:
            sql="INSERT INTO nominee (member_name, party_name, symbol_name) VALUES (%s, %s, %s)"
            cur=mydb.cursor()
            cur.execute(sql, (member, party, logo))
            mydb.commit()
            cur.close()
            flash(r"Successfully registered a new nominee", 'primary')
    return render_template('nominee.html', admin=session['IsAdmin'])

@app.route('/registration', methods=['POST','GET'])
def registration():
    session.pop('aadhar', None)
    session.pop('status', None)
    session.pop('email', None)
    session.pop('otp', None)
    if request.method=='POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        state = request.form['state']
        d_name = request.form['d_name']

        middle_name = request.form['middle_name']
        aadhar_id = request.form['aadhar_id']
        voter_id = request.form['voter_id']
        pno = request.form['pno']
        age = int(request.form['age'])
        email = request.form['email']
        voters=pd.read_sql_query('SELECT * FROM voters', mydb)
        all_aadhar_ids=voters.aadhar_id.values
        all_voter_ids=voters.voter_id.values
        if age >= 18:
            if (aadhar_id in all_aadhar_ids) or (voter_id in all_voter_ids):
                flash(r'Already Registered as a Voter')
            else:
                sql = 'INSERT INTO voters (first_name, middle_name, last_name, aadhar_id, voter_id, email,pno,state,d_name, verified) VALUES (%s,%s,%s, %s, %s, %s, %s, %s, %s, %s)'
                cur=mydb.cursor()
                cur.execute(sql, (first_name, middle_name, last_name, aadhar_id, voter_id, email, pno, state, d_name, 'no'))
                mydb.commit()
                cur.close()
                session['aadhar']=aadhar_id
                session['status']='no'
                session['email']=email
                return redirect(url_for('verify'))
        else:
            flash("if age less than 18 than not eligible for voting","info")
    return render_template('voter_reg.html')

@app.route('/verify', methods=['POST','GET'])
def verify():
    if session['status']=='no':
        if request.method=='POST':
            otp_check=request.form['otp_check']
            if otp_check==session['otp']:
                session['status']='yes'
                sql="UPDATE voters SET verified='%s' WHERE aadhar_id='%s'"%(session['status'], session['aadhar'])
                cur=mydb.cursor()
                cur.execute(sql)
                mydb.commit()
                cur.close()
                flash(r"Email verified successfully",'primary')
                return redirect(url_for('capture_images')) #change it to capture photos
            else:
                flash(r"Wrong OTP. Please try again.","info")
                return redirect(url_for('verify'))
        else:
            #Sending OTP
            message = MIMEMultipart()
            receiver_address = session['email']
            message['From'] = sender_address
            message['To'] = receiver_address
            Otp = str(np.random.randint(100000, 999999))
            session['otp']=Otp
            message.attach(MIMEText(session['otp'], 'plain'))
            abc = smtplib.SMTP('smtp.gmail.com', 587)
            abc.starttls()
            abc.login(sender_address, sender_pass)
            text = message.as_string()
            abc.sendmail(sender_address, receiver_address, text)
            abc.quit()
    else:
        flash(r"Your email is already verified", 'warning')
    return render_template('verify.html')

@app.route('/capture_images', methods=['POST','GET'])
def capture_images():
    if request.method=='POST':
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        font = cv2.FONT_HERSHEY_SIMPLEX
        sampleNum = 0

        # Liveness variables
        blink_count = 0
        eye_closed = False
        REQUIRED_BLINKS = 2
        is_live = False

        path_to_store = os.path.join(os.getcwd(), "all_images\\" + session['aadhar'])
        try:
            shutil.rmtree(path_to_store)
        except:
            pass
        os.makedirs(path_to_store, exist_ok=True)

        while True:
            ret, img = cam.read()
            if not ret:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # ── Liveness Detection ──
            face_detected, eye_ratio, landmarks = check_liveness(img)

            if face_detected:
                if eye_ratio < 0.01:
                    if not eye_closed:
                        eye_closed = True
                elif eye_ratio >= 0.01:
                    if eye_closed:
                        blink_count += 1
                        eye_closed = False
                        print(f"Blink! Count: {blink_count}")

                if blink_count >= REQUIRED_BLINKS:
                    is_live = True

            # ── Show Status on Screen ──
            if not is_live:
                remaining = REQUIRED_BLINKS - blink_count
                cv2.putText(img, f"LIVENESS CHECK: Blink {remaining} more time(s)!",
                           (10, 30), font, 0.7, (0, 0, 255), 2)
                cv2.putText(img, f"Blinks: {blink_count}/{REQUIRED_BLINKS}",
                           (10, 60), font, 0.7, (0, 165, 255), 2)
                cv2.putText(img, "Photo/Fake face will be REJECTED!",
                           (10, 90), font, 0.6, (0, 0, 255), 2)
            else:
                # ── Capture Images only if LIVE ──
                faces = cascade.detectMultiScale(gray, 1.3, 5)

                for (x, y, w, h) in faces:
                    sampleNum += 1
                    face_img = gray[y:y+h, x:x+w]
                    cv2.imwrite(
                        os.path.join(path_to_store, str(sampleNum) + ".jpg"),
                        face_img
                    )
                    cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

                cv2.putText(img, "LIVE PERSON VERIFIED!",
                           (10, 30), font, 0.7, (0, 255, 0), 2)
                cv2.putText(img, f"Capturing: {sampleNum}/200",
                           (10, 60), font, 0.7, (0, 255, 0), 2)
                cv2.putText(img, "Please move face slightly",
                           (10, 90), font, 0.6, (255, 255, 0), 2)

            cv2.imshow('Registration - Liveness Check', img)
            cv2.setWindowProperty('Registration - Liveness Check',
                                 cv2.WND_PROP_TOPMOST, 1)
            cv2.waitKey(100)

            # Auto stop at 200 images
            if sampleNum >= 200:
                break

        cam.release()
        cv2.destroyAllWindows()

        print(f"Total images captured: {sampleNum}")

        # Check enough images captured
        if sampleNum < 50:
            # Delete folder - fake person rejected
            try:
                shutil.rmtree(path_to_store)
            except:
                pass
            # Delete from database also
            sql = "DELETE FROM voters WHERE aadhar_id='%s'" % session['aadhar']
            cur = mydb.cursor()
            cur.execute(sql)
            mydb.commit()
            cur.close()
            flash("Liveness check failed! Fake face detected. Registration rejected.", "danger")
            return redirect(url_for('registration'))

        flash(f"Registration successful! {sampleNum} images captured.", "success")
        return redirect(url_for('home'))

    return render_template('capture.html')

from sklearn.preprocessing import LabelEncoder
import pickle
le = LabelEncoder()

def getImagesAndLabels(path):
    folderPaths = [os.path.join(path, f) for f in os.listdir(path)]
    faces = []
    Ids = []
    global le
    for folder in folderPaths:
        imagePaths = [os.path.join(folder, f) for f in os.listdir(folder)]
        aadhar_id = folder.split("\\")[1]
        for imagePath in imagePaths:
            # loading the image and converting it to gray scale
            pilImage = Image.open(imagePath).convert('L')
            # Now we are converting the PIL image into numpy array
            imageNp = np.array(pilImage, 'uint8')
            # extract the face from the training image sample
            faces.append(imageNp)
            Ids.append(aadhar_id)
            # Ids.append(int(aadhar_id))
    Ids_new=le.fit_transform(Ids).tolist()
    output = open('encoder.pkl', 'wb')
    pickle.dump(le, output)
    output.close()
    return faces, Ids_new

@app.route('/train', methods=['POST','GET'])
def train():
    if request.method=='POST':
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        faces, Id = getImagesAndLabels(r"all_images")
        print(Id)
        print(len(Id))
        recognizer.train(faces, np.array(Id))
        recognizer.save("Trained.yml")
        flash(r"Model Trained Successfully", 'Primary')
        return redirect(url_for('home'))
    return render_template('train.html')
@app.route('/update')
def update():
    return render_template('update.html')
@app.route('/updateback', methods=['POST','GET'])
def updateback():
    if request.method=='POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        middle_name = request.form['middle_name']
        aadhar_id = request.form['aadhar_id']
        voter_id = request.form['voter_id']
        email = request.form['email']
        pno = request.form['pno']
        age = int(request.form['age'])
        voters=pd.read_sql_query('SELECT * FROM voters', mydb)
        all_aadhar_ids=voters.aadhar_id.values
        if age >= 18:
            if (aadhar_id in all_aadhar_ids):
                sql="UPDATE VOTERS SET first_name=%s, middle_name=%s, last_name=%s, voter_id=%s, email=%s,pno=%s, verified=%s where aadhar_id=%s"
                cur=mydb.cursor()
                cur.execute(sql, (first_name, middle_name, last_name, voter_id, email,pno, 'no', aadhar_id))
                mydb.commit()
                cur.close()
                session['aadhar']=aadhar_id
                session['status']='no'
                session['email']=email
                flash(r'Database Updated Successfully','Primary')
                return redirect(url_for('verify'))
            else:
                flash(f"Aadhar: {aadhar_id} doesn't exists in the database for updation", 'warning')
        else:
            flash("age should be 18 or greater than 18 is eligible", "info")
    return render_template('update.html')

def monitor_audio(duration=15):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    THRESHOLD = 80
    THREAT_COUNT = 3

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    print("🎤 Audio monitoring started...")
    frames = []
    threat_count = 0

    for i in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        audio_data = np.frombuffer(data, dtype=np.int16)
        volume = np.abs(audio_data).mean()
        print(f"Volume: {volume:.1f}")

        if volume > THRESHOLD:
            threat_count += 1
            print(f"⚠️ Sound detected! Count: {threat_count}/{THREAT_COUNT}")

        if threat_count >= THREAT_COUNT:
            print("🚨 THREAT DETECTED!")
            audio_threat_detected.set()

            os.makedirs("audio_evidence", exist_ok=True)
            filename = f"audio_evidence/threat_{int(time.time())}.wav"

            stream.stop_stream()
            stream.close()

            wf = wave.open(filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            p.terminate()
            print(f"✅ Evidence saved: {filename}")
            return

    stream.stop_stream()
    stream.close()
    p.terminate()
    print("✅ No threats - Voting allowed")


           
@app.route('/voting', methods=['POST','GET'])
def voting():
    if request.method == 'POST':
        pkl_file = open('encoder.pkl', 'rb')
        my_le = pickle.load(pkl_file)
        pkl_file.close()

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read("Trained.yml")

        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        font = cv2.FONT_HERSHEY_SIMPLEX
        best_aadhar = None
        recognized_count = 0
        REQUIRED_COUNT = 15

        # Liveness variables
        blink_count = 0
        eye_closed = False
        REQUIRED_BLINKS = 2
        is_live = False

        # Random blink challenge variables
        blink_challenge_active = False
        blink_challenge_done = False
        challenge_blink_detected = False
        challenge_window = 2.0  # seconds to blink after voice
        challenge_start_time = None
        challenge_failed = False

        # Start random blink challenge in background
        def run_blink_challenge():
            nonlocal blink_challenge_active, challenge_start_time
            wait_time = random.uniform(1, 7)
            print(f"Challenge akan dimulai setelah {wait_time:.1f} detik")
            time.sleep(wait_time)
            blink_challenge_active = True
            challenge_start_time = time.time()
            print("🔊 Saying: Blink your eyes!")
            tts_engine.say("Blink your eyes")
            tts_engine.runAndWait()

        challenge_thread = threading.Thread(target=run_blink_challenge)
        challenge_thread.daemon = True
        challenge_thread.start()

        while True:
            ret, im = cam.read()
            if not ret:
                continue

            gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)

            # Liveness detection
            face_detected, eye_ratio, landmarks = check_liveness(im)

            if face_detected:
                # Normal blink detection
                if eye_ratio < 0.01:
                    if not eye_closed:
                        eye_closed = True
                elif eye_ratio >= 0.01:
                    if eye_closed:
                        blink_count += 1
                        eye_closed = False
                        print(f"Blink detected: {blink_count}")

                        # Challenge blink check
                        if blink_challenge_active and not blink_challenge_done:
                            if challenge_start_time and \
                               (time.time() - challenge_start_time) <= challenge_window:
                                challenge_blink_detected = True
                                blink_challenge_done = True
                                print("✅ Challenge blink detected in time!")

                if blink_count >= REQUIRED_BLINKS and blink_challenge_done:
                    is_live = True

            # Check if challenge window expired without blink
            if blink_challenge_active and not blink_challenge_done:
                if challenge_start_time and \
                   (time.time() - challenge_start_time) > challenge_window + 3:
                    challenge_failed = True
                    print("❌ Challenge failed - No blink detected in time!")

            # If challenge failed — fake detected
            if challenge_failed:
                cam.release()
                cv2.destroyAllWindows()
                flash("⚠️ Liveness check failed! Possible fake video detected.", "danger")
                return render_template('voting.html')

            # Show status on screen
            if not is_live:
                if blink_challenge_active and not blink_challenge_done:
                    # Challenge active — must blink now!
                    cv2.putText(im, "👁️ BLINK NOW!", (150, 200),
                               font, 2, (0, 0, 255), 4)
                    cv2.putText(im, "Blink immediately!",
                               (150, 260), font, 1, (0, 0, 255), 2)
                else:
                    remaining = REQUIRED_BLINKS - blink_count
                    cv2.putText(im, f"Blink {remaining} more time(s)",
                               (10, 30), font, 0.8, (0, 0, 255), 2)
                    cv2.putText(im, "Wait for voice command...",
                               (10, 60), font, 0.7, (0, 165, 255), 2)
            else:
                cv2.putText(im, "LIVE PERSON VERIFIED!",
                           (10, 30), font, 0.8, (0, 255, 0), 2)

            # Face recognition (only if live)
            if is_live:
                faces = cascade.detectMultiScale(gray, 1.3, 5)
                for (x, y, w, h) in faces:
                    img_h, img_w = im.shape[:2]
                    x = max(0, x)
                    y = max(0, y)
                    w = min(w, img_w - x)
                    h = min(h, img_h - y)
                    if w <= 0 or h <= 0:
                        continue
                    face_crop = gray[y:y+h, x:x+w]
                    if face_crop.size == 0:
                        continue

                    Id, conf = recognizer.predict(face_crop)
                    print(f"Confidence: {conf:.1f}, Count: {recognized_count}")

                    if conf < 70:
                        recognized_count += 1
                        best_aadhar = my_le.inverse_transform([Id])[0]
                        label = f"{best_aadhar} ({int(conf)})"
                        color = (0, 255, 0)
                        cv2.putText(im, f"Identifying: {recognized_count}/{REQUIRED_COUNT}",
                                   (10, 60), font, 0.7, (0, 255, 0), 2)
                    else:
                        recognized_count = 0
                        label = f"Hold still... ({int(conf)})"
                        color = (0, 0, 255)

                    cv2.rectangle(im, (x, y), (x+w, y+h), color, 2)
                    cv2.putText(im, label, (x, y-10), font, 0.7, color, 2)

            cv2.imshow('Voting System', im)
            cv2.setWindowProperty('Voting System', cv2.WND_PROP_TOPMOST, 1)
            cv2.waitKey(30)

            # Auto redirect
            if is_live and recognized_count >= REQUIRED_COUNT:
                cam.release()
                cv2.destroyAllWindows()
                if best_aadhar:
                    session['select_aadhar'] = best_aadhar
                    return redirect(url_for('select_candidate'))
                else:
                    flash("Face not recognized. Try again.", "danger")
                    return render_template('voting.html')

    return render_template('voting.html')
    
@app.route('/select_candidate', methods=['POST','GET'])
def select_candidate():
    aadhar = session['select_aadhar']

    df_nom = pd.read_sql_query('select * from nominee', mydb)
    all_nom = df_nom['symbol_name'].values
    sq = "select * from vote"
    g = pd.read_sql_query(sq, mydb)
    all_adhar = g['aadhar'].values

    if aadhar in all_adhar:
        flash("You already voted", "warning")
        return redirect(url_for('home'))

    else:
        if request.method == 'GET':
            # Audio monitoring শুরু করো
            audio_threat_detected.clear()
            audio_thread = threading.Thread(
                target=monitor_audio,
                args=(15,)
            )
            audio_thread.daemon = True
            audio_thread.start()
            print("🎤 Audio thread started")

        if request.method == 'POST':
            vote = request.form['test']

            # Audio threat check
            if audio_threat_detected.is_set():
                flash("⚠️ Suspicious sound detected near voting booth! Vote NOT registered. Please report to election officer.", "danger")
                audio_threat_detected.clear()
                return redirect(url_for('home'))

            # Vote register করো
            session['vote'] = vote
            sql = "INSERT INTO vote (vote, aadhar) VALUES ('%s', '%s')" % (vote, aadhar)
            cur = mydb.cursor()
            cur.execute(sql)
            mydb.commit()
            cur.close()

            # Voter info
            s = "select * from voters where aadhar_id='" + aadhar + "'"
            c = pd.read_sql_query(s, mydb)
            pno = str(c.values[0][7])
            name = str(c.values[0][1])
            ts = time.time()
            date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            timeStamp = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')

            # SMS
            url = "https://www.fast2sms.com/dev/bulkV2"
            no = "9515851969"
            message = "helloo hai"
            data1 = {
                "route": "q",
                "message": message,
                "language": "english",
                "flash": 0,
                "numbers": no,
            }
            headers = {
                "authorization": "UwmaiQR5OoA6lSTz93nP0tDxsFEhI7VJrfKkvYjbM2C14Wde8g9lvA2Ghq5VNCjrZ4THWkF1KOwp3Bxd",
                "Content-Type": "application/json"
            }
            response = requests.post(url, headers=headers, json=data1)
            print(response)

            # Real-time dashboard update
            votes = pd.read_sql_query('select * from vote', mydb)
            df_nom_live = pd.read_sql_query('select * from nominee', mydb)
            all_nom_live = df_nom_live['symbol_name'].values
            all_party_live = df_nom_live['party_name'].values
            vote_counts = votes['vote'].value_counts()
            all_freqs = []
            for nom in all_nom_live:
                if nom in vote_counts.index:
                    all_freqs.append(int(vote_counts[nom]))
                else:
                    all_freqs.append(0)

            socketio.emit('vote_update', {
                'nominees': list(all_party_live),
                'frequencies': all_freqs,
                'total_votes': int(len(votes)),
                'latest_vote': vote
            })

            flash("✅ Voted Successfully! Environment was safe.", "success")
            return redirect(url_for('home'))

    return render_template('select_candidate.html', noms=sorted(all_nom))

@app.route('/audio_evidence')
def audio_evidence_list():
    if not session.get('IsAdmin'):
        flash("Admin login required!", "danger")
        return redirect(url_for('admin'))
    
    evidence_folder = "audio_evidence"
    files = []
    if os.path.exists(evidence_folder):
        files = os.listdir(evidence_folder)
    
    return render_template('audio_evidence.html', files=files)
@app.route('/voting_res')
def voting_res():
    # Get all votes from database
    votes = pd.read_sql_query('select * from vote', mydb)
    
    # Get all nominees from database
    df_nom = pd.read_sql_query('select * from nominee', mydb)
    all_nom = df_nom['symbol_name'].values
    
    # Count votes for each nominee
    vote_counts = votes['vote'].value_counts()
    
    # Get frequency for each nominee (0 if no votes yet)
    all_freqs = []
    for nom in all_nom:
        if nom in vote_counts.index:
            all_freqs.append(int(vote_counts[nom]))
        else:
            all_freqs.append(0)
    
    print(f"Nominees: {all_nom}")       # check terminal
    print(f"Frequencies: {all_freqs}")  # check terminal
    
    return render_template('voting_res.html', 
                          freq=all_freqs, 
                          noms=all_nom)
    
    
    
@app.route('/dashboard')
def dashboard():
    if not session.get('IsAdmin'):
        flash("Admin login required!", "danger")
        return redirect(url_for('admin'))

    votes = pd.read_sql_query('select * from vote', mydb)
    df_nom = pd.read_sql_query('select * from nominee', mydb)
    df_voters = pd.read_sql_query('select * from voters', mydb)

    # symbol_name = image file (vote table এ এটাই store আছে)
    all_symbols = df_nom['symbol_name'].values
    # party_name = আসল party name (display এর জন্য)
    all_parties = df_nom['party_name'].values

    vote_counts = votes['vote'].value_counts()

    all_freqs = []
    for sym in all_symbols:
        if sym in vote_counts.index:
            all_freqs.append(int(vote_counts[sym]))
        else:
            all_freqs.append(0)

    total_voters = len(df_voters)
    total_votes = len(votes)
    turnout = round((total_votes / total_voters * 100), 1) if total_voters > 0 else 0

    winner = "No votes yet"
    if total_votes > 0:
        winner_idx = all_freqs.index(max(all_freqs))
        winner = all_parties[winner_idx]  

    print(f"Symbols: {all_symbols}")   
    print(f"Parties: {all_parties}")   
    print(f"Freqs: {all_freqs}")        
    print(f"Winner: {winner}")       

    return render_template('dashboard.html',
                          nominees=list(all_parties), 
                          frequencies=all_freqs,
                          total_voters=total_voters,
                          total_votes=total_votes,
                          turnout=turnout,
                          winner=winner)

#if __name__ == '__main__':
#   socketio.run(app, debug=True)
if __name__ == '__main__':
    socketio.run(app, 
                host='0.0.0.0',  # ← for acess in every device
                port=5000,
                debug=True)
    

