import tkinter as tk
import json
import paho.mqtt.client as mqtt
from gpiozero import Servo, MotionSensor
from time import sleep
from datetime import datetime, timedelta
import threading
import csv
import os
import requests
import RPi.GPIO as GPIO

# ----- CSV LOG SETUP -----
log_file = "parking_log.csv"
if not os.path.exists(log_file):
    with open(log_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Plate", "Slot", "Entry Time", "Duration (mins)", "Exit Time", "Type"])

def log_entry(plate, slot, duration, type_):
    entry_time = datetime.now()
    exit_time = entry_time + timedelta(minutes=duration)
    with open(log_file, "a", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([plate, f"Slot {slot}", entry_time.strftime("%Y-%m-%d %H:%M:%S"), duration, exit_time.strftime("%Y-%m-%d %H:%M:%S"), type_])

# ----- SERVO & MOTION SENSOR SETUP -----
servo = Servo(18)
servo.mid()

motion_sensor = MotionSensor(17)  
motion_detected = False

def handle_motion():
    global motion_detected
    motion_detected = True
    print("Motion detected!")

motion_sensor.when_motion = handle_motion

# ----- SLOT STATUS -----
sensor_slot1 = "unknown"
sensor_slot2 = "unknown"
virtual_slot1 = None
virtual_slot2 = None
virtual_timer1 = None
virtual_timer2 = None

# ----- GUI SETUP -----
root = tk.Tk()
root.title("Smart Parking System")
root.geometry("650x650")
root.configure(bg='#f0f0f0')

tk.Label(root, text="Smart Parking System", font=("Arial", 18, "bold"), bg='#f0f0f0').pack(pady=10)

clock_label = tk.Label(root, text="", font=("Arial", 14), bg='#f0f0f0')
clock_label.pack(pady=5)

def update_clock():
    now = datetime.now().strftime("%H:%M:%S")
    clock_label.config(text=f"Current Time: {now}")
    root.after(1000, update_clock)

update_clock()

frame = tk.Frame(root, bg='#f0f0f0')
frame.pack()

slot1_label = tk.Label(frame, text="Slot 1", font=("Arial", 14), bg='#f0f0f0')
slot1_label.grid(row=0, column=0)
canvas1 = tk.Canvas(frame, width=40, height=40)
circle1 = canvas1.create_oval(5, 5, 35, 35, fill="gray")
canvas1.grid(row=1, column=0, padx=20)
slot1_timer = tk.Label(frame, text="", font=("Arial", 10), bg='#f0f0f0')
slot1_timer.grid(row=2, column=0)

slot2_label = tk.Label(frame, text="Slot 2", font=("Arial", 14), bg='#f0f0f0')
slot2_label.grid(row=0, column=1)
canvas2 = tk.Canvas(frame, width=40, height=40)
circle2 = canvas2.create_oval(5, 5, 35, 35, fill="gray")
canvas2.grid(row=1, column=1, padx=20)
slot2_timer = tk.Label(frame, text="", font=("Arial", 10), bg='#f0f0f0')
slot2_timer.grid(row=2, column=1)

tk.Label(root, text="Enter Number Plate:", bg='#f0f0f0').pack(pady=5)
plate_entry = tk.Entry(root, font=("Arial", 14))
plate_entry.pack()

tk.Label(root, text="Parking Time (mins):", bg='#f0f0f0').pack(pady=5)
park_time_entry = tk.Entry(root, font=("Arial", 12))
park_time_entry.pack()

tk.Label(root, text="Enter Email Address:", bg='#f0f0f0').pack(pady=5)
email_entry = tk.Entry(root, font=("Arial", 12))
email_entry.pack()

feedback = tk.Label(root, text="", font=("Arial", 12), bg='#f0f0f0')
feedback.pack(pady=5)

def update_slot_display(data):
    global sensor_slot1, sensor_slot2
    try:
        status = json.loads(data)
        sensor_slot1 = status["slot1"]
        sensor_slot2 = status["slot2"]

        display1 = virtual_slot1 if virtual_slot1 else sensor_slot1
        display2 = virtual_slot2 if virtual_slot2 else sensor_slot2

        color1 = "red" if display1 == "occupied" else "green"
        canvas1.itemconfig(circle1, fill=color1)

        color2 = "red" if display2 == "occupied" else "green"
        canvas2.itemconfig(circle2, fill=color2)

    except Exception as e:
        print("Error parsing MQTT:", e)

def open_gate():
    feedback.config(text="✅ Gate Opening...")
    servo.max()
    root.update()
    sleep(2)
    servo.mid()
    sleep(1)
    feedback.config(text="")

def start_virtual_timer(slot, minutes, plate, email):
    end_time = datetime.now() + timedelta(minutes=minutes)

    def countdown():
        global virtual_slot1, virtual_slot2
        while datetime.now() < end_time:
            remaining = end_time - datetime.now()
            mins, secs = divmod(int(remaining.total_seconds()), 60)
            if slot == 1:
                slot1_timer.config(text=f"Time left: {mins:02d}:{secs:02d}")
            else:
                slot2_timer.config(text=f"Time left: {mins:02d}:{secs:02d}")
            sleep(1)

        if slot == 1:
            slot1_timer.config(text="")
            if sensor_slot1 == "vacant":
                virtual_slot1 = None
        else:
            slot2_timer.config(text="")
            if sensor_slot2 == "vacant":
                virtual_slot2 = None

        update_slot_display(json.dumps({"slot1": sensor_slot1, "slot2": sensor_slot2}))

        try:
            webhook_url = "https://maker.ifttt.com/trigger/notify_exit/with/key/bSW-pjwaTVX4dZA_cZLxhp"
            data = {
                "value1": f"Slot {slot}",
                "value2": plate,
                "value3": email
            }
            requests.post(webhook_url, json=data)
            print("IFTTT Webhook triggered.")
        except Exception as e:
            print(f"Failed to send IFTTT webhook: {e}")

    thread = threading.Thread(target=countdown)
    if slot == 1:
        global virtual_timer1
        virtual_timer1 = thread
    else:
        global virtual_timer2
        virtual_timer2 = thread
    thread.start()

def check_plate():
    global virtual_slot1, virtual_slot2, motion_detected
    plate = plate_entry.get().strip().upper()
    email = email_entry.get().strip()

    if not plate:
        feedback.config(text="❌ Please enter a plate number.")
        return
    if not email or "@" not in email:
        feedback.config(text="❌ Enter a valid email address.")
        return

    try:
        minutes = int(park_time_entry.get())
        if minutes <= 0:
            raise ValueError
    except ValueError:
        feedback.config(text="❌ Enter a valid parking time.")
        return

    display1 = virtual_slot1 if virtual_slot1 else sensor_slot1
    display2 = virtual_slot2 if virtual_slot2 else sensor_slot2

    slot1_free = (display1 == "vacant")
    slot2_free = (display2 == "vacant")

    if not motion_detected:
        feedback.config(text="❌ Motion not detected. Please approach the gate.")
        return

    if slot1_free:
        virtual_slot1 = "occupied"
        slot_used = 1
        start_virtual_timer(1, minutes, plate, email)
    elif slot2_free:
        virtual_slot2 = "occupied"
        slot_used = 2
        start_virtual_timer(2, minutes, plate, email)
    else:
        feedback.config(text="❌ Access denied. No space available.")
        servo.mid()
        return

    update_slot_display(json.dumps({"slot1": sensor_slot1, "slot2": sensor_slot2}))
    feedback.config(text=f"✅ Slot {slot_used} reserved for {minutes} minutes.")
    log_entry(plate, slot_used, minutes, "Temporary")
    open_gate()

    motion_detected = False  # Reset after opening gate

    plate_entry.delete(0, tk.END)
    park_time_entry.delete(0, tk.END)
    email_entry.delete(0, tk.END)

tk.Button(root, text="Check & Enter", font=("Arial", 12), command=check_plate).pack(pady=10)

# ----- MQTT -----
def on_connect(client, userdata, flags, rc):
    print("MQTT connected")
    client.subscribe("archit/parking")

def on_message(client, userdata, msg):
    root.after(0, update_slot_display, msg.payload.decode())

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("broker.hivemq.com", 1883, 60)

def mqtt_loop():
    client.loop(timeout=0.1)
    root.after(100, mqtt_loop)

mqtt_loop()
root.mainloop()
