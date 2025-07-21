import os
import time
import re
import streamlit as st
import requests
from dotenv import load_dotenv
from io import BytesIO
from pydub import AudioSegment
from pydub.utils import which

# Verifica se o FFmpeg está disponível
if not which("ffmpeg"):
    st.error("FFmpeg não está instalado ou não está no PATH do sistema. O processamento de áudio pode falhar.")

# Carrega as chaves do Azure via Streamlit Secrets
try:
    AZURE_SPEECH_KEY = st.secrets["AZURE_SPEECH_KEY"]
    AZURE_SPEECH_REGION = st.secrets.get("AZURE_REGION", "brazilsouth")
except KeyError:
    st.error("Chave de API Azure não encontrada! Verifique as configurações de 'Secrets'. Ex: AZURE_SPEECH_KEY e AZURE_REGION")
    st.stop()

# Configuração da API
ENDPOINT = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
HEADERS = {
    "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
    "Content-Type": "application/ssml+xml",
    "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3"
}

# Vozes disponíveis
VOICES = {
    "Camila - Feminina (pt-BR)": "pt-BR-FranciscaNeural",
    "Daniel - Masculina (pt-BR)": "pt-BR-AntonioNeural",
    "Igual Google Tradutor": "pt-BR-BrendaNeural",
    "Narrador - Neutro": "pt-BR-CelioNeural"
}

# Geração do SSML
def generate_ssml(text, voice_name, rate="0%"):
    return f"""
    <speak version='1.0' xml:lang='pt-BR'>
        <voice name='{voice_name}'>
            <prosody rate="{rate}">{text}</prosody>
        </voice>
    </speak>
    """

# Requisição para TTS
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
                st.error(f"Erro na conversão do bloco (HTTP {response.status_code}): {error_message}")
                return None
        except requests.RequestException as e:
            if attempt < retries:
                st.warning(f"Tentativa {attempt + 1}/{retries + 1}: Erro de conexão. Tentando novamente...")
                time.sleep(2)
            else:
                st.error("Não foi possível conectar ao serviço Azure TTS.")
                st.exception(e)
                return None

# Quebra de texto
def split_text(text, max_length=4000):
    paragraphs = re.split(r'(?<=[.!?])\s+', text.strip())
    blocks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 1 <= max_length:
            current += p + " "
        else:
            blocks.append(current.strip())
            current = p + " "
    if current:
        blocks.append(current.strip())

    return blocks

# Interface Streamlit
st.set_page_config(page_title="Conversor de Texto em Áudio", page_icon=None, layout="centered")

st.title("Conversor de Texto em Áudio")
st.markdown("---")

text = st.text_area("Texto para converter em áudio:", height=200, placeholder="Digite o texto desejado.")
voice = st.selectbox("Escolha a voz:", list(VOICES.keys()))
rate = st.slider("Velocidade da fala (%)", -50, 50, 0, step=10)

# Informações sobre o texto
char_count = len(text.strip())
if char_count:
    text_parts = split_text(text)
    st.info(f"Total de caracteres digitados: {char_count}")
    st.success(f"O texto será processado em {len(text_parts)} bloco(s).")
else:
    st.info("Digite um texto acima para ver os detalhes.")

st.markdown("---")

if st.button("Converter Texto em Áudio"):
    if not text.strip():
        st.warning("Digite um texto antes de converter.")
        st.stop()

    voice_selected = VOICES.get(voice, "pt-BR-FranciscaNeural")
    audio_segments = []
    success_count = 0

    st.subheader("Processando Áudio")
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, part in enumerate(text_parts, start=1):
        status_text.text(f"Processando bloco {idx} de {len(text_parts)}...")
        audio_bytes = text_to_speech(part, voice_selected, rate=f"{rate}%")
        progress_bar.progress(idx / len(text_parts))

        with st.expander(f"Bloco {idx}"):
            st.write(part)

        if audio_bytes:
            try:
                segment = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
                audio_segments.append(segment)
                st.success(f"Bloco {idx} gerado com sucesso.")
                success_count += 1
            except Exception as e:
                st.error(f"Erro ao processar o áudio do bloco {idx}. Verifique se o FFmpeg está instalado.")
                st.exception(e)
        else:
            st.error(f"Falha ao gerar o bloco {idx}. Verifique os erros acima.")

    status_text.text("Processamento de blocos concluído.")
    st.markdown("---")

    st.subheader("Resultados")
    st.info(f"""
Resumo Final:
- Total de caracteres digitados: {char_count}
- Blocos processados com sucesso: {success_count} de {len(text_parts)}
""")

    if success_count == len(text_parts) and audio_segments:
        st.info("Concatenando os áudios gerados...")

        try:
            combined = sum(audio_segments)
            mp3_buffer = BytesIO()
            combined.export(mp3_buffer, format="mp3")
            mp3_data = mp3_buffer.getvalue()

            st.success("Áudio completo gerado com sucesso.")
            st.audio(mp3_data, format="audio/mp3")
            st.download_button("Baixar Áudio Completo (MP3)", data=mp3_data, file_name="audio_completo.mp3", mime="audio/mp3")

        except Exception as e:
            st.error("Erro ao exportar o áudio final.")
            st.exception(e)
    elif not audio_segments:
        st.warning("Nenhum bloco foi gerado com sucesso. Nada para concatenar.")
    else:
        st.warning("Nem todos os blocos foram gerados. A concatenação completa não é possível.")

st.markdown("---")
st.markdown("Feito por [Viviane](https://github.com/vsantosj)")
