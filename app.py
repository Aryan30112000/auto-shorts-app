import streamlit as st
import os
import asyncio
import tempfile
from PIL import Image
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, vfx

st.set_page_config(page_title="Auto Shorts Maker", layout="centered")
st.title("📱 Auto Shorts Generator")

# 1. API Setup
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
else:
    st.error("API Key सेटिंग्स में नहीं मिली! कृपया Streamlit Secrets चेक करें।")
    st.stop()

uploaded_file = st.file_uploader("अपना पोस्टर अपलोड करें", type=["jpg", "jpeg", "png"])

if uploaded_file and st.button("🚀 Video Generate Karein"):
    with st.spinner("AI वीडियो बना रहा है, कृपया 10-15 सेकंड प्रतीक्षा करें..."):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_img_path = os.path.join(tmpdir, "input.jpg")
                audio_path = os.path.join(tmpdir, "voice.mp3")
                output_vid_path = os.path.join(tmpdir, "short.mp4")

                with open(input_img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # 1. Script Generation using Gemini 3.6 Flash
                pil_image = Image.open(input_img_path)
                prompt = (
                    "इस पोस्टर को पढ़ो और केवल 15 सेकंड की आकर्षक, बोलने वाली हिंदी स्क्रिप्ट लिखो। "
                    "शुरुआत में सवाल हो और अंत में 'YES या NO कमेंट करें' कहें। "
                    "सिर्फ बोलने वाला टेक्स्ट दो, कोई निर्देश, ब्रैकेट या इमोजी नहीं।"
                )
                
                try:
                    model = genai.GenerativeModel("models/gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])
                except Exception:
                    # Alternative fallback name
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])

                script = res.text.strip()
                st.info(f"**जनरेटेड स्क्रिप्ट:**\n\n{script}")

                # 2. Free Voiceover (Edge-TTS)
                async def generate_audio():
                    comm = edge_tts.Communicate(script, voice="hi-IN-MadhurNeural")
                    await comm.save(audio_path)

                asyncio.run(generate_audio())

                # 3. Video Editing (MoviePy)
                import numpy as np
from PIL import ImageFilter

# 3. Video Editing (Clean & Glitch-Free 9:16 Format)
audio = AudioFileClip(audio_path)
duration = audio.duration

# ओरिजिनल इमेज लोड करें
orig_img = Image.open(input_img_path)

# (A) बैकग्राउंड: फुल 1080x1920 पर ब्लर इमेज
bg_img = orig_img.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(15))
bg_path = os.path.join(tmpdir, "bg.jpg")
bg_img.save(bg_path)
bg_clip = ImageClip(bg_path).set_duration(duration)

# (B) फोरग्राउंड: ओरिजिनल पोस्टर बिना कटे बीच में फिट
fg_clip = ImageClip(input_img_path).set_duration(duration)
fg_clip = fg_clip.resize(width=1000)  # स्क्रीन पर सुंदर फिट
fg_clip = fg_clip.set_position("center")

# दोनों को कंबाइन करें
from moviepy.editor import CompositeVideoClip
final_clip = CompositeVideoClip([bg_clip, fg_clip], size=(1080, 1920))
final_clip = final_clip.set_audio(audio)

final_clip.write_videofile(
    output_vid_path, 
    fps=24, 
    codec="libx264", 
    audio_codec="aac",
    preset="ultrafast",
    ffmpeg_params=["-pix_fmt", "yuv420p"]
)
                # 4. Display & Download
                st.success("🎉 वीडियो तैयार है!")
                st.video(output_vid_path)
                
                with open(output_vid_path, "rb") as vid_file:
                    st.download_button(
                        label="📥 Download Video",
                        data=vid_file.read(),
                        file_name="auto_short.mp4",
                        mime="video/mp4"
                    )

        except Exception as e:
            st.error(f"Error: {e}")
