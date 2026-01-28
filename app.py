from flask import Flask, render_template, request, send_file, after_this_request
import requests
import yt_dlp  # IMPORTANTE: Requer 'pip install yt-dlp'
import os
import time

app = Flask(__name__)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    formato_usuario = request.form.get('format') 

    # --- ESTRATÉGIA 1: TIKTOK (Usa API Externa - Mais Rápido) ---
    if "tiktok.com" in url:
        try:
            api_url = "https://www.tikwm.com/api/"
            payload = {'url': url, 'count': 12, 'cursor': 0, 'web': 1, 'hd': 1}
            response = requests.post(api_url, data=payload)
            data = response.json()

            if 'data' not in data:
                return f"Erro: Vídeo não encontrado ou privado. Detalhes: {data}", 400
            
            # Escolhe o link (MP3 ou MP4)
            if formato_usuario == 'mp3':
                link_final = data['data']['music']
                extensao = 'mp3'
            else:
                link_final = data['data']['play']
                extensao = 'mp4'
            
            # Correção de link cortado
            if not link_final.startswith('http'):
                link_final = f"https://www.tikwm.com{link_final}"

            # Baixa o arquivo
            arquivo = requests.get(link_final)
            filename = f"{DOWNLOAD_FOLDER}/tiktok_baixado.{extensao}"
            
            with open(filename, 'wb') as f:
                f.write(arquivo.content)

            # Função de limpeza
            @after_this_request
            def remove_file(response):
                try:
                    time.sleep(2)
                    if os.path.exists(filename):
                        os.remove(filename)
                except Exception as error:
                    app.logger.error(f"Erro ao remover: {error}")
                return response

            return send_file(filename, as_attachment=True)

        except Exception as e:
            return f"Erro na API do TikTok: {str(e)}", 400

    # --- ESTRATÉGIA 2: YOUTUBE & INSTAGRAM (Usa yt-dlp - Mais Robusto) ---
    else:
        try:
            # Configurações do yt-dlp
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True,
            }

            # Configura formato MP3 ou MP4
            if formato_usuario == 'mp3':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                ydl_opts.update({
                    'format': 'bestvideo+bestaudio/best', # Tenta baixar a melhor qualidade
                    'merge_output_format': 'mp4',          # Garante que saia em MP4
                })

            # Tenta baixar com yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                # Ajuste de nome para MP3 (o yt-dlp muda a extensão no final)
                if formato_usuario == 'mp3':
                    base, _ = os.path.splitext(filename)
                    filename = base + ".mp3"

                @after_this_request
                def remove_file(response):
                    try:
                        time.sleep(2)
                        if os.path.exists(filename):
                            os.remove(filename)
                    except Exception as error:
                        app.logger.error(f"Erro ao remover: {error}")
                    return response

                return send_file(filename, as_attachment=True)

        except Exception as e:
            return f"Erro ao baixar (YouTube/Insta): {str(e)}", 400

if __name__ == '__main__':
    app.run(debug=True)