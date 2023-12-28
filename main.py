import time

from flask import Flask, request, jsonify
from flask.cli import load_dotenv
from pyVoIP.VoIP import VoIPPhone, VoIPCall
import os
from twilio.rest import Client
import threading
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

app = Flask(__name__)

# Twilio configuration
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
twilio_client = Client(account_sid, auth_token)

# Thread-safe dictionary for verification info
verification_info = {}


# Function to load DTMF tone files
def load_dtmf_tone(digit):
    filename = f"./tones/audiocheck.net_dtmf_{digit}.wav"
    with open(filename, 'rb') as file:
        return file.read()


# Callback function for incoming calls
def handle_call(call: VoIPCall):
    try:
        call_session_id = call.session_id
        call.answer()

        if call_session_id in verification_info:
            code = verification_info[call_session_id]['verification_code']
            for digit in str(code):
                tone_data = load_dtmf_tone(digit)
                call.write_audio(tone_data)
                time.sleep(0.5)  # Wait for 500ms before playing the next digit

        call.hangup()
    except Exception as e:
        print(f"Error during call handling: {e}")


# Endpoint to initiate a verification request
@app.route('/start-verification', methods=['POST'])
def start_verification():
    data = request.json
    phone_number = data.get('phone_number')
    friendly_name = data.get('friendly_name', 'Third Party VOIP Number')

    validation_request = twilio_client.validation_requests.create(
        friendly_name=friendly_name,
        # status_callback='https://your_callback_url_here',  # Update this URL
        phone_number=phone_number
    )

    # Store verification info
    call_session_id = validation_request.call_sid  # Assuming this is a unique identifier
    verification_info[call_session_id] = {
        'phone_number': phone_number,
        'verification_code': validation_request.validation_code
    }

    # todo loki logging

    return jsonify(validation_request.friendly_name)


# Initialize the VoIPPhone
def start_phone():
    phone = VoIPPhone(server=os.getenv('VOIP_SERVER_IP'),
                      port=int(os.getenv('VOIP_SERVER_PORT', 5060)),
                      username=os.getenv('VOIP_USERNAME'),
                      password=os.getenv('VOIP_PASSWORD'),
                      callCallback=handle_call,
                      myIP=os.getenv('VOIP_LOCAL_IP'),
                      rtpPortLow=int(os.getenv('VOIP_RTP_PORT_LOW', 10000)),
                      rtpPortHigh=int(os.getenv('VOIP_RTP_PORT_HIGH', 20000)))
    phone.start()
    return phone


if __name__ == "__main__":
    voip_thread = threading.Thread(target=start_phone)
    voip_thread.start()
    app.run(debug=True, use_reloader=False, host="0.0.0.0")
    voip_thread.join()
