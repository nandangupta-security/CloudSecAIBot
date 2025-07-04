from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import subprocess
import os
import json

app = Flask(__name__)
CORS(app)

@app.route('/.well-known/openapi.json')
def serve_openapi():
    return send_from_directory(os.path.join(app.root_path, 'static/.well-known'), 'openapi.json')

@app.route("/run-aws", methods=["POST"])
def run_aws():
    data = request.json
    command = data.get("command")
    print(command)

    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return jsonify({"text": result.decode("utf-8")})
    except subprocess.CalledProcessError as e:
        return jsonify({"text": e.output.decode("utf-8")}), 500

@app.route("/iam/users-without-mfa", methods=["GET"])
def users_without_mfa():
    try:
        # Get list of all IAM users
        users_output = subprocess.check_output("aws iam list-users", shell=True)
        users = json.loads(users_output.decode("utf-8"))["Users"]

        users_without_mfa = []

        for user in users:
            username = user["UserName"]
            mfa_cmd = f"aws iam list-mfa-devices --user-name {username}"
            mfa_output = subprocess.check_output(mfa_cmd, shell=True)
            mfa_devices = json.loads(mfa_output.decode("utf-8"))["MFADevices"]

            if len(mfa_devices) == 0:
                users_without_mfa.append(username)

        output_text = "\n".join(users_without_mfa) if users_without_mfa else "All users have MFA enabled."
        return jsonify({"text": output_text})
    
    except subprocess.CalledProcessError as e:
        return jsonify({"text": e.output.decode("utf-8")}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)
