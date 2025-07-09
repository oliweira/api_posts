# api_posts/app.py

from flask import Flask, request, jsonify, send_from_directory
import pymysql.cursors
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask_cors import CORS

# --- Importações para o APScheduler ---
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import atexit # Para garantir que o scheduler pare ao fechar o app

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Configurações ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Configurações do Banco de Dados
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    try:
        connection = pymysql.connect(host=DB_HOST,
                                     user=DB_USER,
                                     password=DB_PASSWORD,
                                     database=DB_NAME,
                                     cursorclass=pymysql.cursors.DictCursor)
        return connection
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

# --- Funções de Publicação (MOCK - Simulação) ---
# Aqui é onde a lógica de integração real com Instagram/WhatsApp irá
def publish_to_instagram(post_data):
    """Simula a publicação no Instagram."""
    print(f"[{datetime.now()}] PUBLICANDO NO INSTAGRAM: Legenda='{post_data['legenda']}' Mídia='{post_data['caminho_midia']}'")
    # Lógica REAL de API do Instagram viria aqui
    # Ex: requests.post(INSTAGRAM_API_URL, data=...)
    return True # Simula sucesso

def publish_to_whatsapp(post_data):
    """Simula a publicação no WhatsApp."""
    print(f"[{datetime.now()}] PUBLICANDO NO WHATSAPP: Legenda='{post_data['legenda']}' Mídia='{post_data['caminho_midia']}'")
    # Lógica REAL de automação do WhatsApp viria aqui
    # Cuidado com soluções não oficiais, como discutido.
    return True # Simula sucesso

# --- Função do Agendador para Processar Posts ---
def process_scheduled_posts():
    """
    Verifica o banco de dados por posts agendados que já passaram da hora
    e tenta publicá-los.
    """
    print(f"[{datetime.now()}] Verificando posts agendados...")
    connection = get_db_connection()
    if connection is None:
        print("Não foi possível conectar ao DB para processar posts agendados.")
        return

    try:
        with connection.cursor() as cursor:
            # Seleciona posts agendados que ainda não foram publicados e cuja data de agendamento é no passado
            sql = "SELECT * FROM posts WHERE status = 'agendado' AND data_agendamento <= %s"
            cursor.execute(sql, (datetime.now(),))
            posts_to_publish = cursor.fetchall()

        for post in posts_to_publish:
            print(f"[{datetime.now()}] Processando post ID {post['id']}: {post['legenda']}")
            success = True
            platforms_list = post['plataformas'].split(',') # Converte a string de plataformas de volta para lista

            if 'instagram' in platforms_list:
                if not publish_to_instagram(post):
                    success = False
            
            if 'whatsapp' in platforms_list:
                if not publish_to_whatsapp(post):
                    success = False # Se falhar em uma, marca como falha geral

            # Atualiza o status do post no banco de dados
            new_status = 'publicado' if success else 'erro'
            data_publicacao = datetime.now() if success else None # Se for erro, pode deixar null ou colocar erro time

            with connection.cursor() as cursor:
                update_sql = "UPDATE posts SET status = %s, data_publicacao = %s WHERE id = %s"
                cursor.execute(update_sql, (new_status, data_publicacao, post['id']))
            connection.commit()
            print(f"[{datetime.now()}] Post ID {post['id']} atualizado para status: {new_status}")

    except Exception as e:
        print(f"[{datetime.now()}] Erro geral no processamento de posts agendados: {e}")
        connection.rollback()
    finally:
        connection.close()

# --- Configuração do APScheduler ---
# Cria um scheduler de background
scheduler = BackgroundScheduler()
# Adiciona uma job que roda a cada 10 segundos para verificar posts
# Você pode ajustar este intervalo (e.g., 'minutes=1' para 1 minuto)
scheduler.add_job(process_scheduled_posts, 'interval', seconds=10)

# --- Rotas da API (mantidas as mesmas) ---
@app.route('/posts', methods=['POST'])
def create_post():
    legenda = request.form.get('legenda')
    tipo_midia = request.form.get('tipo_midia') 
    plataformas = request.form.get('plataformas')
    data_agendamento_str = request.form.get('data_agendamento')

    if 'file' not in request.files:
        return jsonify({"message": "Nenhum arquivo enviado"}), 400
    
    file = request.files['file']

    if file.filename == '':
        return jsonify({"message": "Nome de arquivo vazio"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        caminho_midia_para_db = file_path
    else:
        return jsonify({"message": "Tipo de arquivo não permitido"}), 400

    if not all([legenda, tipo_midia, plataformas, data_agendamento_str]):
        os.remove(file_path)
        return jsonify({"message": "Campos obrigatórios ausentes"}), 400

    try:
        data_agendamento = datetime.fromisoformat(data_agendamento_str)
    except ValueError:
        os.remove(file_path)
        return jsonify({"message": "Formato de data e hora inválido. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}), 400

    connection = get_db_connection()
    if connection is None:
        os.remove(file_path)
        return jsonify({"message": "Erro de conexão com o banco de dados"}), 500

    try:
        with connection.cursor() as cursor:
            sql = """INSERT INTO posts (legenda, caminho_midia, tipo_midia, plataformas, data_agendamento)
                     VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(sql, (legenda, caminho_midia_para_db, tipo_midia, plataformas, data_agendamento))
        connection.commit()
        return jsonify({"message": "Post criado com sucesso!", "id": cursor.lastrowid, "file_path": caminho_midia_para_db}), 201
    except Exception as e:
        connection.rollback()
        os.remove(file_path)
        print(f"Erro ao inserir post no banco: {e}")
        return jsonify({"message": "Erro ao criar post", "error": str(e)}), 500
    finally:
        connection.close()

@app.route('/posts', methods=['GET'])
def get_posts():
    connection = get_db_connection()
    if connection is None:
        return jsonify({"message": "Erro de conexão com o banco de dados"}), 500

    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM posts ORDER BY data_agendamento DESC"
            cursor.execute(sql)
            posts = cursor.fetchall()
            
            for post in posts:
                # Flask serve arquivos estáticos de forma simples.
                # A URL deve ser construída de forma que o Flask Static Files possa encontrá-lo.
                # Por padrão, Flask serve arquivos estáticos de 'static' ou do 'root_path'.
                # Como UPLOAD_FOLDER está na raiz, precisamos expô-lo.
                # A rota /uploads/<filename> já faz isso.
                if post['caminho_midia'] and os.path.exists(post['caminho_midia']):
                    # Extrai apenas o nome do arquivo para usar na URL da rota /uploads
                    filename_only = os.path.basename(post['caminho_midia'])
                    post['url_midia'] = request.url_root + 'uploads/' + filename_only
                else:
                    post['url_midia'] = None
        return jsonify(posts), 200
    except Exception as e:
        print(f"Erro ao buscar posts no banco: {e}")
        return jsonify({"message": "Erro ao buscar posts", "error": str(e)}), 500
    finally:
        connection.close()

# Rota para servir arquivos estáticos (como as mídias uploaded)
# Certifique-se que o Flask saiba onde buscar.
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# --- Execução do Servidor Flask ---
if __name__ == '__main__':
    # Inicia o scheduler quando o aplicativo Flask inicia
    scheduler.start()
    print("Scheduler iniciado.")

    # Garante que o scheduler seja desligado ao sair do aplicativo
    atexit.register(lambda: scheduler.shutdown())

    app.run(debug=True, port=5000)