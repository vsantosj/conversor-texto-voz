import os
import time
import streamlit as st
import requests
from dotenv import load_dotenv
from io import BytesIO
from pydub import AudioSegment

try:
    AZURE_SPEECH_KEY = st.secrets["AZURE_SPEECH_KEY"]
    AZURE_SPEECH_REGION = st.secrets.get("AZURE_REGION", "brazilsouth") 
except KeyError:
    st.error("❌ **Chave de API Azure não encontrada!** Verifique as configurações de 'Secrets' no seu aplicativo Streamlit. Ex: AZURE_SPEECH_KEY e AZURE_REGION")
    st.stop()


ENDPOINT = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
HEADERS = {
    "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
    "Content-Type": "application/ssml+xml",
    "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3"
}

VOICES = {
    "Camila - Feminina (pt-BR)": "pt-BR-FranciscaNeural",
    "Daniel - Masculina (pt-BR)": "pt-BR-AntonioNeural",
    "Igual Google Tradutor": "pt-BR-BrendaNeural",
    "Narrador - Neutro": "pt-BR-CelioNeural"
}

def generate_ssml(text, voice_name, rate="0%"):
    return f"""
    <speak version='1.0' xml:lang='pt-BR'>
        <voice name='{voice_name}'>
            <prosody rate="{rate}">{text}</prosody>
        </voice>
    </speak>
    """

def text_to_speech(text, voice_name, rate="0%", retries=2):
    ssml = generate_ssml(text, voice_name, rate)
    for attempt in range(retries + 1):
        try:
            response = requests.post(
                ENDPOINT,
                headers=HEADERS,
                data=ssml.encode("utf-8"),
                timeout=15 
            )
            if response.status_code == 200:
                return response.content
            else:
                try:
                    error_message = response.json().get("error", {}).get("message", response.text)
                except requests.exceptions.JSONDecodeError:
                    error_message = response.text 
                st.error(f"Erro na conversão do bloco (HTTP {response.status_code}):** {error_message}")
                return None
        except requests.RequestException as e:
            if attempt < retries:
                st.warning(f"⚠️ Tentativa {attempt + 1}/{retries + 1}: Erro de conexão. Tentando novamente em 2 segundos...")
                time.sleep(2)
                continue
            else:
                st.error("**Erro fatal!** Não foi possível conectar ao serviço Azure TTS após várias tentativas.")
                st.exception(e)
                return None

def split_text(text, max_length=4000):
    parts = []
    text = text.strip()

    while len(text) > max_length:
        split_pos = text.rfind('.', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(' ', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
        else:
            split_pos += 1

        parts.append(text[:split_pos].strip())
        text = text[split_pos:].strip()

    if text:
        parts.append(text)

    return parts


st.set_page_config(
    page_title="Conversor de Texto em Áudio",
    page_icon="🗣️", # Ícone da aba do navegador
    layout="centered"
)

st.title("🗣️ Conversor de Texto em Áudio")
st.markdown("Transforme qualquer texto em fala natural usando o poder da inteligência artificial da Azure. Ideal para criar narrações, audiobooks ou conteúdo acessível. ✨")
st.markdown("---")

text = st.text_area("Digite o texto para converter em áudio:", height=200, placeholder="Ex: Olá! Bem-vindo ao meu aplicativo de conversão de texto em áudio. Digite aqui o que você gostaria de ouvir.")
voice = st.selectbox("🎙️ Escolha a voz:", list(VOICES.keys()))
rate = st.slider("⚡️ Velocidade da fala (%)", -50, 50, 0, step=10, help="Ajusta a velocidade da fala. Valores negativos deixam a fala mais lenta, positivos mais rápida.")

if text.strip():
    text_parts = split_text(text)
    st.info(f"🧾 Seu texto tem **{len(text)} caracteres** e será processado em **{len(text_parts)} bloco(s)**.")
else:
    st.info("⌨️ Por favor, digite um texto acima para converter em áudio.")

st.markdown("---") # Separador para organizar a interface

if st.button("▶️ Converter Texto em Áudio"):

    if not text.strip():
        st.warning("⚠️ **Atenção!** Você precisa digitar um texto para converter.")
        st.stop()

    voice_selected = VOICES.get(voice, "pt-BR-FranciscaNeural")
    audio_segments = []
    success_count = 0

    st.subheader("Processamento de Áudio 🎧")
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, part in enumerate(text_parts, start=1):
        status_text.text(f"⏳ Processando bloco {idx} de {len(text_parts)}...")
        audio_bytes = text_to_speech(part, voice_selected, rate=f"{rate}%")
        
        progress_bar.progress((idx) / len(text_parts)) # Atualiza a barra de progresso
        
        if audio_bytes:
            try:
                segment = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
                audio_segments.append(segment)
                st.success(f"✅ Bloco {idx} gerado com sucesso.")
                success_count += 1
            except Exception as e:
                st.error(f"Erro ao processar o áudio do bloco {idx} com pydub. Verifique se FFmpeg está instalado. Detalhes: {e}")
                # Não para o app, mas continua para outros blocos
        else:
            st.error(f"Falha crítica ao gerar o bloco {idx}. Verifique logs acima para mais detalhes.")
            # Se um bloco falha, não podemos concatenar tudo no final, mas continuamos para ver outros erros
            
    status_text.text("Processamento de blocos concluído!")
    st.markdown("---")

    st.subheader("Resultados ✨")
    st.info(f"**Resumo:** Total de caracteres: **{len(text)}** | Blocos processados com sucesso: **{success_count} de {len(text_parts)}**")

    if success_count == len(text_parts) and audio_segments: # Garante que todos foram gerados e há segmentos
        st.info("🔄 **Concatenando todos os áudios gerados...** Isso pode levar alguns segundos. 🔊")
        
        try:
            combined = sum(audio_segments)
            mp3_buffer = BytesIO()
            combined.export(mp3_buffer, format="mp3")
            mp3_data = mp3_buffer.getvalue()

            st.success("🎉 **Áudio completo gerado com sucesso!**")
            st.audio(mp3_data, format="audio/mp3", help="Ouça seu áudio aqui.")
            st.download_button(
                label="⬇️ Baixar Áudio Completo (MP3)",
                data=mp3_data,
                file_name="audio_completo.mp3",
                mime="audio/mp3"
            )
        except Exception as e:
            st.error(f"**Erro ao concatenar ou exportar o áudio final.** Detalhes: {e}")
            st.warning("Pode haver um problema com os segmentos de áudio gerados ou com a instalação do FFmpeg.")
    elif not audio_segments:
        st.warning(" **Nenhum bloco de áudio foi gerado com sucesso.** Não há áudio para concatenar.")
    else:
        st.warning("**Nem todos os blocos foram gerados com sucesso.** A concatenação do áudio completo não é possível. Verifique os erros acima.")

st.markdown("---")
st.markdown("Feito por [Viviane](https://github.com/vsantosj)")
