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

# Helper function to auto-detect working model
def generate_script_auto(pil_img, prompt_text):
    # Get all available models for this key
    available_models = [
        m.name for m in genai.list_models() 
        if "generateContent" in m.supported_generation_methods
    ]
    
    # Priority order for models
    preferred = [
        "models/gemini-1.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-pro",
        "models/gemini-pro-vision",
        "models/gemini-pro"
    ]
    
    selected_model_name = None
    for pref in preferred:
        if pref in available_models:
            selected_model_name = pref
            break
            
    if not selected_model_name and available_models:
        selected_model_name = available_models[0]
        
    if not selected_model_name:
        raise Exception("आपकी API Key के लिए कोई एक्टिव मॉडल नहीं मिला। कृपया aistudio.google.com पर नई Key बनाएं।")
        
    model = genai.GenerativeModel(selected_model_name)
    response = model.generate_content([pil_img, prompt_text])
    return response.text.strip(), selected_model_name

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

                # 1. Auto-detected Model Script
                pil_image = Image.open(input_img_path)
                prompt = (
                    "इस पोस्टर को पढ़ो और केवल 15 सेकंड की आकर्षक, बोलने वाली हिंदी स्क्रिप्ट लिखो। "
                    "शुरुआत में सवाल हो और अंत में 'YES या NO कमेंट करें' कहें। "
                    "सिर्फ बोलने वाला टेक्स्ट दो, कोई निर्देश या इमोजी नहीं।"
                )
                
                script, used_model = generate_script_auto(pil_image, prompt)
                st.info(f"**जनरेटेड स्क्रिप्ट ({used_model.replace('models/', '')}):**\n\n{script}")

                # 2. Free Voiceover (Edge-TTS)
                async def generate_audio():
                    comm = edge_tts.Communicate(script, voice="hi-IN-MadhurNeural")
                    await comm.save(audio_path)

                asyncio.run(generate_audio())

                # 3. Video Editing (MoviePy)
                audio = AudioFileClip(audio_path)
                clip = ImageClip(input_img_path).set_duration(audio.duration)
                
                # 9:16 Shorts Format & Zoom Motion
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
