from flask import Flask, render_template, request, send_file, after_this_request
import requests
import yt_dlp
import os
import time
import subprocess
import shutil

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
    qualidade_escolhida = request.form.get('format') 

    # ==============================================================================
    # ESTRATÉGIA 1: TIKTOK (TikWM + Conversão Segura)
    # ==============================================================================
    if "tiktok.com" in url:
        try:
            # 1. Pega o link da API (TikWM para evitar bloqueios)
            headers_tiktok = {'User-Agent': 'Mozilla/5.0'}
            api_url = "https://www.tikwm.com/api/"
            payload = {'url': url, 'count': 12, 'cursor': 0, 'web': 1, 'hd': 1}
            
            response = requests.post(api_url, data=payload, headers=headers_tiktok)
            data = response.json()

            if 'data' not in data:
                return f"Erro: Vídeo não encontrado. Detalhes: {data}", 400
            
            # 2. Define o link correto baseado na escolha
            if qualidade_escolhida == 'mp3':
                link_final = data['data']['music']
                extensao_final = 'mp3'
            elif qualidade_escolhida in ['360', '480']:
                link_final = data['data']['play']
                extensao_final = 'mp4'
            else:
                link_final = data['data'].get('hdplay', data['data']['play'])
                extensao_final = 'mp4'
            
            if not link_final.startswith('http'):
                link_final = f"https://www.tikwm.com{link_final}"

            # 3. Baixa o arquivo Bruto para um nome temporário
            arquivo_remoto = requests.get(link_final, headers=headers_tiktok)
            
            # Nome temporário (bruto) e nome final (que o usuário vai receber)
            nome_temp = f"{DOWNLOAD_FOLDER}/temp_{int(time.time())}"
            nome_final = f"{DOWNLOAD_FOLDER}/tiktok_{int(time.time())}.{extensao_final}"

            with open(nome_temp, 'wb') as f:
                f.write(arquivo_remoto.content)

            # 4. TENTATIVA DE CONVERSÃO (MODO SEGURO)
            # Se for MP3, tentamos converter usando o FFmpeg do servidor
            if qualidade_escolhida == 'mp3':
                try:
                    # Tenta converter (Vai funcionar no Render)
                    subprocess.run([
                        'ffmpeg', '-y', '-i', nome_temp, 
                        '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', 
                        nome_final
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Se deu certo, remove o temporário antigo
                    if os.path.exists(nome_temp):
                        os.remove(nome_temp)
                        
                except (FileNotFoundError, Exception):
                    # SE FALHAR (No seu PC Windows sem FFmpeg), apenas renomeia o original
                    # Assim o download não quebra com erro 400!
                    print("AVISO: FFmpeg não encontrado ou erro. Enviando arquivo original renomeado.")
                    if os.path.exists(nome_temp):
                        if os.path.exists(nome_final):
                            os.remove(nome_final)
                        os.rename(nome_temp, nome_final)
            else:
                # Se for vídeo, não precisa converter, só renomeia
                if os.path.exists(nome_temp):
                    if os.path.exists(nome_final):
                        os.remove(nome_final)
                    os.rename(nome_temp, nome_final)

            # 5. Limpeza com espera maior (Resolve o WinError 32)
            @after_this_request
            def remove_file(response):
                try:
                    time.sleep(5) # Aumentei para 5s para o Windows liberar o arquivo
                    if os.path.exists(nome_final):
                        os.remove(nome_final)
                except Exception as error:
                    # Apenas imprime o erro no console, não trava o site
                    print(f"Erro ao limpar (ignorado): {error}")
                return response

            return send_file(nome_final, as_attachment=True)

        except Exception as e:
            return f"Erro no TikTok: {str(e)}", 400

    # ==============================================================================
    # ESTRATÉGIA 2: YOUTUBE & INSTAGRAM (yt-dlp)
    # ==============================================================================
    else:
        try:
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True,
                'nocheckcertificate': True,
                'geo_bypass': True,
                # Estratégia Android para evitar bloqueio 403
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'], 
                        'player_skip': ['webpage', 'configs', 'js'], 
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36',
                    'Accept-Language': 'en-us,en;q=0.5',
                }
            }

            # Configurações de Qualidade
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
                ydl_opts.update({'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best', 'merge_output_format': 'mp4'})
            elif qualidade_escolhida == '480':
                ydl_opts.update({'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best', 'merge_output_format': 'mp4'})
            elif qualidade_escolhida == '360':
                ydl_opts.update({'format': 'bestvideo[height<=360]+bestaudio/best[height<=360]/best', 'merge_output_format': 'mp4'})
            else:
                ydl_opts.update({'format': 'bestvideo+bestaudio/best', 'merge_output_format': 'mp4'})

            # Executa o download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                # Verifica se a conversão aconteceu (Modo Seguro também aqui)
                if qualidade_escolhida == 'mp3':
                    nome_mp3 = os.path.splitext(filename)[0] + ".mp3"
                    if os.path.exists(nome_mp3):
                        filename = nome_mp3
                    # Se não existir (erro no FFmpeg local), ele manda o original
                else:
                    if filename.endswith('.webm') or filename.endswith('.mkv'):
                        nome_mp4 = os.path.splitext(filename)[0] + '.mp4'
                        if os.path.exists(nome_mp4):
                            filename = nome_mp4

                @after_this_request
                def remove_file(response):
                    try:
                        time.sleep(5) # 5 segundos de segurança
                        if os.path.exists(filename):
                            os.remove(filename)
                    except Exception as error:
                        print(f"Erro ao limpar: {error}")
                    return response

                return send_file(filename, as_attachment=True)

        except Exception as e:
            return f"Erro ao baixar: {str(e)}", 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)