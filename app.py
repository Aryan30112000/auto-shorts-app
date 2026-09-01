import streamlit as st
import os
import asyncio
from PIL import Image
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, vfx
import tempfile

st.set_page_config(page_title="Auto Shorts Maker", layout="centered")
st.title("📱 Auto Shorts Generator")

# 1. API Setup
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API Key सेटिंग्स में नहीं मिली! कृपया Streamlit Secrets चेक करें।")
    st.stop()

uploaded_file = st.file_uploader("अपना पोस्टर अपलोड करें", type=["jpg", "jpeg", "png"])

if uploaded_file and st.button("🚀 Video Generate Karein"):
    with st.spinner("AI वीडियो बना रहा है, कृपया 10-15 सेकंड प्रतीक्षा करें..."):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_img_path = os.path.join(tmpdir, "input.jpg")
            audio_path = os.path.join(tmpdir, "voice.mp3")
            output_vid_path = os.path.join(tmpdir, "short.mp4")

            # पोस्टर सेव करें
            with open(input_img_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # 1. Gemini से हिंदी स्क्रिप्ट (सीधे PIL Image पास करके)
            model = genai.GenerativeModel("gemini-1.5-flash")
            pil_image = Image.open(input_img_path)
            
            prompt = (
                "इस पोस्टर को पढ़ो और केवल 15 सेकंड की आकर्षक, बोलने वाली हिंदी स्क्रिप्ट लिखो। "
                "शुरुआत में सवाल हो और अंत में 'YES या NO कमेंट करें' कहें। "
                "सिर्फ बोलने वाला टेक्स्ट दो, कोई निर्देश या इमोजी नहीं।"
            )
            res = model.generate_content([pil_image, prompt])
            script = res.text.strip()
            st.info(f"**जनरेटेड स्क्रिप्ट:** {script}")

            # 2. Voiceover (Edge-TTS)
            async def generate_audio():
                comm = edge_tts.Communicate(script, voice="hi-IN-MadhurNeural")
                await comm.save(audio_path)

            asyncio.run(generate_audio())

            # 3. Video Editing (MoviePy)
            audio = AudioFileClip(audio_path)
            clip = ImageClip(input_img_path).set_duration(audio.duration)
            
            # 9:16 Shorts Format & Subtle Motion
            clip = clip.resize(height=1920)
            clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
            clip = clip.fx(vfx.resize, lambda t: 1 + 0.03 * (t / audio.duration))
            clip = clip.set_audio(audio)
            
            clip.write_videofile(output_vid_path, fps=24, codec="libx264", audio_codec="aac")

            # 4. Show & Download
            st.success("🎉 वीडियो तैयार है!")
            st.video(output_vid_path)
            
            with open(output_vid_path, "rb") as vid_file:
                st.download_button(
                    label="📥 Download Video",
                    data=vid_file.read(),
                    file_name="auto_short.mp4",
                    mime="video/mp4"
                )
