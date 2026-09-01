import streamlit as st
import os
import asyncio
import base64
import requests
import tempfile
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, vfx

st.set_page_config(page_title="Auto Shorts Maker", layout="centered")
st.title("📱 Auto Shorts Generator")

# 1. API Setup Check
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"].strip()
else:
    st.error("API Key सेटिंग्स में नहीं मिली! कृपया Streamlit Secrets में GEMINI_API_KEY चेक करें।")
    st.stop()

uploaded_file = st.file_uploader("अपना पोस्टर अपलोड करें", type=["jpg", "jpeg", "png"])

# Direct REST API Helper Function
def get_script_from_gemini(image_bytes, mime_type, api_key):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt = (
        "इस पोस्टर को पढ़ो और केवल 15 सेकंड की आकर्षक, बोलने वाली हिंदी स्क्रिप्ट लिखो। "
        "शुरुआत में सवाल हो और अंत में 'YES या NO कमेंट करें' कहें। "
        "सिर्फ बोलने वाला टेक्स्ट दो, कोई निर्देश, ब्रैकेट या इमोजी नहीं।"
    )
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64_image
                    }
                }
            ]
        }]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    res_data = response.json()
    
    if "error" in res_data:
        raise Exception(f"Gemini API Error: {res_data['error'].get('message', 'Unknown Error')}")
        
    return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()

if uploaded_file and st.button("🚀 Video Generate Karein"):
    with st.spinner("AI वीडियो बना रहा है, कृपया 10-15 सेकंड प्रतीक्षा करें..."):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_img_path = os.path.join(tmpdir, "input.jpg")
                audio_path = os.path.join(tmpdir, "voice.mp3")
                output_vid_path = os.path.join(tmpdir, "short.mp4")

                file_bytes = uploaded_file.getvalue()
                mime_type = uploaded_file.type or "image/jpeg"

                with open(input_img_path, "wb") as f:
                    f.write(file_bytes)

                # 1. Script Generation via REST API
                script = get_script_from_gemini(file_bytes, mime_type, API_KEY)
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
