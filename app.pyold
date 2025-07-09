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
def publish_to_instagram(post_data):
    """Simula a publicação no Instagram."""
    media_source = post_data.get('caminho_midia') 
    print(f"[{datetime.now()}] PUBLICANDO NO INSTAGRAM: Legenda='{post_data['legenda']}' Mídia='{media_source}'")
    return True 

def publish_to_whatsapp(post_data):
    """Simula a publicação no WhatsApp."""
    media_source = post_data.get('caminho_midia')
    print(f"[{datetime.now()}] PUBLICANDO NO WHATSAPP: Legenda='{post_data['legenda']}' Mídia='{media_source}'")
    return True 

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
            sql = "SELECT * FROM posts WHERE status = 'agendado' AND data_agendamento <= %s"
            cursor.execute(sql, (datetime.now(),))
            posts_to_publish = cursor.fetchall()

        for post in posts_to_publish:
            print(f"[{datetime.now()}] Processando post ID {post['id']}: {post['legenda']}")
            success = True
            platforms_list = post['plataformas'].split(',')

            if 'instagram' in platforms_list:
                if not publish_to_instagram(post):
                    success = False
            
            if 'whatsapp' in platforms_list:
                if not publish_to_whatsapp(post):
                    success = False

            new_status = 'publicado' if success else 'erro'
            data_publicacao = datetime.now() if success else None

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
scheduler = BackgroundScheduler()
scheduler.add_job(process_scheduled_posts, 'interval', seconds=10)

# --- Rotas da API ---

@app.route('/posts', methods=['POST'])
def create_post():
    legenda = request.form.get('legenda')
    tipo_midia = request.form.get('tipo_midia') 
    plataformas = request.form.get('plataformas')
    data_agendamento_str = request.form.get('data_agendamento')
    url_midia_form = request.form.get('url_midia') # Pega a URL do formulário (se houver)

    caminho_midia_para_db = None # Variável para armazenar o valor final de 'caminho_midia' no DB

    # Lida com o upload de arquivo primeiro
    if 'media_file' in request.files and request.files['media_file'].filename != '':
        file = request.files['media_file']
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            # CORREÇÃO: Garante que o caminho no DB use forward slashes
            caminho_midia_para_db = file_path.replace('\\', '/') 
        else:
            return jsonify({"message": "Tipo de arquivo não permitido"}), 400
    elif url_midia_form: # Se nenhum arquivo, mas uma URL externa é fornecida
        base_url_for_uploads = request.url_root + 'uploads/'
        if url_midia_form.startswith(base_url_for_uploads):
            # É uma URL de um arquivo local, extrai o caminho relativo
            caminho_midia_para_db = url_midia_form[len(request.url_root):].replace('\\', '/') 
        else:
            # É uma URL externa, salva como está
            caminho_midia_para_db = url_midia_form 
    
    # Se nem arquivo nem URL foram fornecidos, retorna erro (mídia é obrigatória)
    if not caminho_midia_para_db and url_midia_form is None:
         return jsonify({"message": "Mídia (arquivo ou URL) é obrigatória"}), 400

    if not all([legenda, tipo_midia, plataformas, data_agendamento_str]):
        if caminho_midia_para_db and os.path.exists(caminho_midia_para_db.replace('/', os.sep)):
            os.remove(caminho_midia_para_db.replace('/', os.sep))
        return jsonify({"message": "Campos obrigatórios ausentes"}), 400

    try:
        data_agendamento = datetime.fromisoformat(data_agendamento_str.replace('Z', '+00:00'))
    except ValueError:
        if caminho_midia_para_db and os.path.exists(caminho_midia_para_db.replace('/', os.sep)):
            os.remove(caminho_midia_para_db.replace('/', os.sep))
        return jsonify({"message": "Formato de data e hora inválido. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)"}), 400

    connection = get_db_connection()
    if connection is None:
        if caminho_midia_para_db and os.path.exists(caminho_midia_para_db.replace('/', os.sep)):
            os.remove(caminho_midia_para_db.replace('/', os.sep))
        return jsonify({"message": "Erro de conexão com o banco de dados"}), 500

    try:
        with connection.cursor() as cursor:
            sql = """INSERT INTO posts (legenda, caminho_midia, tipo_midia, plataformas, data_agendamento)
                     VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(sql, (legenda, caminho_midia_para_db, tipo_midia, plataformas, data_agendamento))
        connection.commit()
        return jsonify({"message": "Post criado com sucesso!", "id": cursor.lastrowid}), 201
    except Exception as e:
        connection.rollback()
        if caminho_midia_para_db and os.path.exists(caminho_midia_para_db.replace('/', os.sep)):
            os.remove(caminho_midia_para_db.replace('/', os.sep))
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
                # Gera 'url_midia' dinamicamente para o frontend
                if post['caminho_midia']:
                    # Normalize o caminho do DB para o formato do sistema de arquivos para o os.path.exists
                    local_path_normalized_for_os = post['caminho_midia'].replace('/', os.sep)
                    if os.path.exists(local_path_normalized_for_os):
                        filename_only = os.path.basename(post['caminho_midia']) # Usa o original do DB, que já está '/'
                        post['url_midia'] = request.url_root + 'uploads/' + filename_only
                    else:
                        post['url_midia'] = post['caminho_midia']
                else:
                    post['url_midia'] = None
                
        return jsonify(posts), 200
    except Exception as e:
        print(f"Erro ao buscar posts no banco: {e}")
        return jsonify({"message": "Erro ao buscar posts", "error": str(e)}), 500
    finally:
        connection.close()

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    connection = get_db_connection()
    if connection is None:
        return jsonify({"message": "Erro de conexão com o banco de dados"}), 500

    try:
        with connection.cursor() as cursor:
            sql_select = "SELECT * FROM posts WHERE id = %s"
            cursor.execute(sql_select, (post_id,))
            post = cursor.fetchone()
            if not post:
                return jsonify({"message": "Post não encontrado"}), 404

            legenda = request.form.get('legenda')
            tipo_midia = request.form.get('tipo_midia')
            plataformas = request.form.get('plataformas')
            data_agendamento_str = request.form.get('data_agendamento')
            url_midia_form = request.form.get('url_midia') # URL vinda do frontend (pode ser vazia ou completa)

            if not all([legenda, tipo_midia, plataformas, data_agendamento_str]):
                return jsonify({"message": "Campos obrigatórios ausentes"}), 400

            try:
                data_agendamento = datetime.fromisoformat(data_agendamento_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({"message": "Formato de data e hora inválido. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)"}), 400

            new_caminho_midia = post['caminho_midia'] # Começa com o valor atual do banco de dados

            is_file_uploaded = 'media_file' in request.files and request.files['media_file'].filename != ''
            is_url_field_sent_by_frontend = 'url_midia' in request.form 
            
            # Flag para controlar a exclusão do arquivo local antigo
            delete_old_local_file = False

            if is_file_uploaded:
                media_file = request.files['media_file']
                if allowed_file(media_file.filename):
                    # Um novo arquivo foi enviado, então sempre planejar a exclusão do antigo se ele existia e era local
                    delete_old_local_file = True 
                    filename = secure_filename(media_file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    media_file.save(filepath)
                    # CORREÇÃO: Garante que o caminho no DB use forward slashes
                    new_caminho_midia = filepath.replace('\\', '/') 
                else:
                    return jsonify({"message": "Tipo de arquivo não permitido"}), 400
            elif is_url_field_sent_by_frontend:
                # O campo 'url_midia' foi enviado do frontend (pode estar vazio ou com uma URL)
                if url_midia_form == '':
                    # Usuário explicitamente limpou o campo de URL
                    new_caminho_midia = None # Define 'caminho_midia' como NULL no DB
                    delete_old_local_file = True # Se o antigo era local, deve ser excluído
                else:
                    # Usuário forneceu uma string de URL (pode ser a URL de um arquivo local existente ou uma nova URL externa)
                    base_url_for_uploads = request.url_root + 'uploads/'
                    if url_midia_form.startswith(base_url_for_uploads):
                        # É uma URL para um dos nossos próprios arquivos enviados (ex: http://.../uploads/arquivo.jpg)
                        # Extrai apenas a parte relativa "uploads/arquivo.jpg" para salvar no DB
                        # CORREÇÃO: Garante que o caminho extraído use forward slashes
                        extracted_relative_path = url_midia_form[len(request.url_root):].replace('\\', '/')
                        
                        # Normalize o caminho antigo para comparação
                        normalized_old_caminho_midia = post['caminho_midia'].replace('\\', '/') if post['caminho_midia'] else None

                        # Verifica se o caminho antigo (se local) é diferente do novo caminho relativo extraído
                        # E se o antigo caminho realmente existe no sistema de arquivos
                        if normalized_old_caminho_midia and os.path.exists(normalized_old_caminho_midia.replace('/', os.sep)) and normalized_old_caminho_midia != extracted_relative_path:
                            delete_old_local_file = True # Se for diferente, planeja a exclusão do antigo
                        
                        new_caminho_midia = extracted_relative_path # Salva "uploads/nome.ext"
                    else:
                        # É uma URL externa (ou alguma outra string que não aponta para nossos uploads)
                        new_caminho_midia = url_midia_form
                        # Se o antigo era um arquivo local, mas estamos mudando para uma URL externa, exclui o antigo
                        if post['caminho_midia'] and os.path.exists(post['caminho_midia'].replace('/', os.sep)):
                            delete_old_local_file = True 
            
            # --- Executa a exclusão do arquivo local antigo, se a flag estiver ativada ---
            # CORREÇÃO: Normaliza o caminho do DB para o formato do sistema de arquivos antes de verificar a existência e excluir
            if delete_old_local_file and post['caminho_midia']:
                local_path_to_delete = post['caminho_midia'].replace('/', os.sep)
                if os.path.exists(local_path_to_delete):
                    os.remove(local_path_to_delete)
                    print(f"Antigo arquivo de mídia '{post['caminho_midia']}' excluído do servidor.")

            # --- Agora atualiza o banco de dados ---
            sql_update = """
                UPDATE posts SET
                legenda = %s,
                caminho_midia = %s, # Agora armazenará o caminho relativo correto ou a URL externa
                tipo_midia = %s,
                plataformas = %s,
                data_agendamento = %s
                WHERE id = %s
            """
            cursor.execute(sql_update, (
                legenda,
                new_caminho_midia,
                tipo_midia,
                plataformas,
                data_agendamento,
                post_id
            ))
            connection.commit()

            # Busca o post atualizado para retornar a resposta e prepara 'url_midia' para o frontend
            cursor.execute(sql_select, (post_id,))
            updated_post_data = cursor.fetchone()

            # Gera 'url_midia' dinamicamente para o frontend na resposta
            if updated_post_data['caminho_midia']:
                # Normaliza o caminho do DB para o formato do sistema de arquivos para o os.path.exists
                local_path_normalized_for_os = updated_post_data['caminho_midia'].replace('/', os.sep)
                if os.path.exists(local_path_normalized_for_os):
                    filename_only = os.path.basename(updated_post_data['caminho_midia'])
                    updated_post_data['url_midia'] = request.url_root + 'uploads/' + filename_only
                else:
                    updated_post_data['url_midia'] = updated_post_data['caminho_midia']
            else:
                updated_post_data['url_midia'] = None

            return jsonify({"message": "Post atualizado com sucesso!", "post": updated_post_data}), 200

    except Exception as e:
        connection.rollback()
        print(f"Erro ao atualizar post no banco: {e}")
        return jsonify({"message": "Erro ao atualizar post", "error": str(e)}), 500
    finally:
        connection.close()

@app.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    connection = get_db_connection()
    if connection is None:
        return jsonify({"message": "Erro de conexão com o banco de dados"}), 500

    try:
        with connection.cursor() as cursor:
            sql_select = "SELECT caminho_midia FROM posts WHERE id = %s"
            cursor.execute(sql_select, (post_id,))
            post = cursor.fetchone()

            if not post:
                return jsonify({"message": "Post não encontrado"}), 404

            # CORREÇÃO: Normaliza o caminho do DB para o formato do sistema de arquivos antes de verificar a existência e excluir
            if post['caminho_midia']:
                local_path_to_delete = post['caminho_midia'].replace('/', os.sep)
                if os.path.exists(local_path_to_delete):
                    os.remove(local_path_to_delete)
                    print(f"Arquivo de mídia '{post['caminho_midia']}' excluído do servidor.")

            sql_delete = "DELETE FROM posts WHERE id = %s"
            cursor.execute(sql_delete, (post_id,))
        connection.commit()
        return jsonify({"message": "Post excluído com sucesso"}), 200
    except Exception as e:
        connection.rollback()
        print(f"Erro ao excluir post: {e}")
        return jsonify({"message": "Erro ao excluir post", "error": str(e)}), 500
    finally:
        connection.close()

# --- Execução do Servidor Flask ---
if __name__ == '__main__':
    scheduler.start()
    print("Scheduler iniciado.")
    atexit.register(lambda: scheduler.shutdown())
    app.run(debug=True, port=5000)