from flask import Flask, render_template, request, send_file, after_this_request
import requests
import yt_dlp
import os
import time

app = Flask(__name__)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/termos')
def terms():
    return render_template('terms.html')

@app.route('/politica')
def privacy():
    return render_template('privacy.html')

@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    # O formato agora pode receber: 'best', '720', '480', '360' ou 'mp3'
    qualidade_escolhida = request.form.get('format') 

    # --- ESTRATÉGIA 1: TIKTOK (Usa API Externa - Mais Rápido) ---
    if "tiktok.com" in url:
        try:
            api_url = "https://www.tikwm.com/api/"
            payload = {'url': url, 'count': 12, 'cursor': 0, 'web': 1, 'hd': 1}
            response = requests.post(api_url, data=payload)
            data = response.json()

            if 'data' not in data:
                return f"Erro: Vídeo não encontrado ou privado. Detalhes: {data}", 400
            
            # Lógica de Escolha para TikTok
            if qualidade_escolhida == 'mp3':
                link_final = data['data']['music']
                extensao = 'mp3'
            elif qualidade_escolhida in ['360', '480']:
                # Se o usuário quer economia (360 ou 480), pegamos a versão normal 'play'
                link_final = data['data']['play']
                extensao = 'mp4'
            else:
                # Se quer 720 ou Máxima, tentamos a versão HD ('hdplay')
                # Se não tiver HD, o .get pega a versão normal como garantia
                link_final = data['data'].get('hdplay', data['data']['play'])
                extensao = 'mp4'
            
            # Correção de link cortado
            if not link_final.startswith('http'):
                link_final = f"https://www.tikwm.com{link_final}"

            # Baixa o arquivo manualmente
            arquivo = requests.get(link_final)
            filename = f"{DOWNLOAD_FOLDER}/tiktok_{int(time.time())}.{extensao}"
            
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

    # --- ESTRATÉGIA 2: YOUTUBE & INSTAGRAM (Usa yt-dlp - Com Seletor de Qualidade) ---
    else:
        try:
            # Configurações básicas do yt-dlp
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True,
            }

            # --- LÓGICA DETALHADA DE QUALIDADE ---
            if qualidade_escolhida == 'mp3':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            
            elif qualidade_escolhida == '720':
                # Tenta baixar 720p ou inferior
                ydl_opts.update({'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'})
                ydl_opts.update({'merge_output_format': 'mp4'})
            
            elif qualidade_escolhida == '480':
                # Tenta baixar 480p ou inferior
                ydl_opts.update({'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best'})
                ydl_opts.update({'merge_output_format': 'mp4'})

            elif qualidade_escolhida == '360':
                # Tenta baixar 360p ou inferior (Super Leve)
                ydl_opts.update({'format': 'bestvideo[height<=360]+bestaudio/best[height<=360]/best'})
                ydl_opts.update({'merge_output_format': 'mp4'})

            else:
                # 'best' -> Baixa a máxima qualidade disponível (pode ser 1080p, 4K, etc)
                ydl_opts.update({'format': 'bestvideo+bestaudio/best'})
                ydl_opts.update({'merge_output_format': 'mp4'})

            # Executa o download com yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                # Ajuste de nome para MP3 (o yt-dlp muda a extensão no final)
                if qualidade_escolhida == 'mp3':
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
    # Define a porta correta para o Render ou usa 5000 localmente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)