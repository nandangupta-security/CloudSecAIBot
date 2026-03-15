System Requirements
RequirementDetailsPython3.8 or higherRAMMinimum 8 GB (16 GB recommended)Disk SpaceAt least 5 GB freeOSWindows 10/11, macOS 10.15+, or LinuxInternetRequired only for the initial model downloadGPUOptional — NVIDIA CUDA speeds things up, but CPU works fine

No GPU? No problem. The script automatically falls back to CPU. Responses will take 1–3 minutes per reply but will work correctly.


Installation
Step 1 — Check your Python version
bashpython --version
You need Python 3.8 or higher. Download from python.org if needed.
Step 2 — Install dependencies
bashpip install torch
pip install transformers==4.40.2

Important: Pin transformers to 4.40.2. Newer versions (5.x) have a breaking incompatibility with Phi-3 Mini's rope_scaling config that causes a KeyError: 'type' crash on startup.

Save the script
Save simplechatbot.py to a folder of your choice, for example your Desktop or a folder named workshop.

Running the Chatbot
Launch the script
python simplechatbot.py
What happens on first run
StepWhat's happening1Model files download from Hugging Face (~3.8 GB, one time only)2Model loads into RAM — takes 20–60 seconds3You: prompt appears — type your message and press Enter4Response is generated — 1–3 min on CPU, ~10 sec on GPU
Exiting
Type x and press Enter at any time:
You: x
Goodbye!

Troubleshooting
ProblemSolutionKeyError: 'type' on startupRun pip install transformers==4.40.2 and try againModuleNotFoundError: transformersRun pip install transformers==4.40.2ModuleNotFoundError: torchRun pip install torchModel loads but no response printsMake sure you are running the latest version of the scriptOut of memory / process killedClose other apps. 8 GB RAM minimum required.Download is very slowThe model is ~3.8 GB. It only downloads once — subsequent runs load from disk.Response takes 1–3 minutesNormal on CPU. A GPU will reduce this to under 10 seconds.
Quick Reference
Install:
bashpip install torch
pip install transformers==4.40.2
Run:
bashpython simplechatbot.py
Exit: type x and press Enter