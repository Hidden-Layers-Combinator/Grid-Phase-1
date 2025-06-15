import streamlit as st
import google.generativeai as genai
import os
import re
import subprocess
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip
import tempfile # For temporary file management
import shutil # For cleaning up temporary directories

# Set your Gemini API Key
# IMPORTANT: Replace "GEMINI_API_KEY" with the actual key in your .streamlit/secrets.toml
# Example .streamlit/secrets.toml:
# GEMINI_API_KEY = "YOUR_ACTUAL_GEMINI_API_KEY_HERE"
try:
    genai.configure(api_key="AIzaSyArJnjxicFsu60Ns6Sx7v92rkK_bBywd3k")
except KeyError:
    st.error("Gemini API Key not found. Please set it in .streamlit/secrets.toml")
    st.stop()

st.title("🧠 Grid: Animated Math & Physics Explainer")

query = st.text_area("📩 Enter your problem statement (math/physics):")

if st.button("Generate Video"):
    if not query.strip():
        st.warning("Please enter a valid query.")
        st.stop()

    # Create a temporary directory for each session to avoid file conflicts
    with tempfile.TemporaryDirectory() as temp_dir:
        manim_file = os.path.join(temp_dir, "Animation.py")
        video_file = os.path.join(temp_dir, "video.mp4")
        audio_file = os.path.join(temp_dir, "voiceover.mp3")
        final_video_file = os.path.join(temp_dir, "final.mp4")

        with st.spinner("🧠 Generating animation and script with Gemini..."):
            prompt = f"""
You are a helpful assistant for an educational platform called "Grid".

Given a student's query, generate:
1. A Python animated lecture using the Manim library (Scene class name: AnimationScene). Animation generated should by clean, no overlapping, fadeout previous before another slide.
2. A short English voiceover script that syncs with the animation such like teacher is teaching donot include 'pause' or any other instructions.

🧠 Requirements:
- Every sentence in the voiceover should correspond to a specific part of the animation.
- Use wait() and run_time= parameters in Manim to match timing (~2–3 sec per step).
- Do NOT use external assets like SVGMobject, images, or external files.
- Return only code and script in the following format:

<manim>
# Manim code
</manim>

<voiceover>
# Voiceover script
</voiceover>

Student Query:
"{query}"
"""
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                output = response.text
            except Exception as e:
                st.error(f"❌ Gemini API call failed: {e}")
                st.stop()

            # Parse Manim and Voiceover
            manim_code_match = re.search(r"<manim>(.*?)</manim>", output, re.DOTALL)
            voiceover_match = re.search(r"<voiceover>(.*?)</voiceover>", output, re.DOTALL)

            if not manim_code_match or not voiceover_match:
                st.error("Could not parse Gemini output. Please try again or refine your query.")
                st.text_area("Raw Gemini Output (for debugging):", output, height=300)
                st.stop()

            manim_code = manim_code_match.group(1).strip()
            voice_text = voiceover_match.group(1).strip()

        # Clean and save Manim code
        clean_code = manim_code.replace("```python", "").replace("```", "").strip()

        with open(manim_file, "w") as f:
            f.write(clean_code)

        st.subheader("Generated Manim Code:")
        st.code(clean_code, language="python")

        st.subheader("Generated Voiceover Script:")
        st.write(voice_text)

        with st.spinner("🎞 Rendering animation using Manim..."):
            try:
                # Use --output_file to specify the exact output path
                result = subprocess.run([
                    "manim", "-ql", manim_file, "AnimationScene", "--output_file", video_file
                ], capture_output=True, text=True, check=True) # check=True will raise CalledProcessError
            except subprocess.CalledProcessError as e:
                st.error(f"❌ Manim rendering failed with exit code {e.returncode}.")
                st.text_area("🔧 Error Log (Manim STDOUT):", e.stdout)
                st.text_area("🔧 Error Log (Manim STDERR):", e.stderr)
                st.stop()
            except FileNotFoundError:
                st.error("❌ Manim command not found. Please ensure Manim is installed and in your system's PATH.")
                st.stop()
            except Exception as e:
                st.error(f"❌ An unexpected error occurred during Manim rendering: {e}")
                st.stop()

            if not os.path.exists(video_file):
                st.error("❌ Manim rendering completed, but output video file was not found.")
                st.stop()

        with st.spinner("🔊 Generating voiceover..."):
            try:
                tts = gTTS(voice_text)
                tts.save(audio_file)
            except Exception as e: # gTTS specific exceptions could be caught here for more detail
                st.error(f"❌ Failed to generate voiceover: {e}")
                st.stop()

            if not os.path.exists(audio_file):
                st.error("❌ gTTS generated, but audio file was not found.")
                st.stop()

        with st.spinner("🎬 Merging audio and video..."):
            try:
                video = VideoFileClip(video_file)
                audio = AudioFileClip(audio_file)
                final = video.set_audio(audio)
                # Use output_file for MoviePy as well
                final.write_videofile(final_video_file, codec="libx264", audio_codec="aac")
                video.close() # Important to close clips to release resources
                audio.close()
            except FileNotFoundError:
                st.error("❌ Video or audio file not found for merging. Ensure Manim and gTTS worked correctly.")
                st.stop()
            except Exception as e: # More specific MoviePy/FFmpeg errors could be caught here
                st.error(f"❌ Failed to merge audio and video. This might be due to FFmpeg not being installed or accessible. Error: {e}")
                st.text_area("MoviePy Error Details:", str(e)) # Display error details if available
                st.stop()

            if not os.path.exists(final_video_file):
                st.error("❌ Video merging completed, but final video file was not found.")
                st.stop()

        st.success("✅ Your final explainer video is ready:")
        st.video(final_video_file)

    # Temporary directory and its contents will be automatically deleted here
