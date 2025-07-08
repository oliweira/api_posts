# app.py

from flask import Flask, request, jsonify
import pymysql.cursors
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename # Importar para segurança no nome do arquivo
from flask_cors import CORS # Importar CORS para permitir requisições do frontend

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app) # Habilita CORS para todas as rotas (importante para o React)

# --- Configurações ---
# Pasta onde os uploads serão salvos
UPLOAD_FOLDER = 'uploads'
# Lista de extensões de arquivos permitidas (você pode adicionar mais)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Cria a pasta de uploads se ela não existir
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Configurações do Banco de Dados (carregadas de .env)
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Função para obter uma conexão com o banco de dados."""
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

# --- Rotas da API ---

@app.route('/posts', methods=['POST'])
def create_post():
    """Endpoint para criar um novo post com upload de arquivo."""
    
    # 1. Obtenção dos dados do formulário e do arquivo
    # Quando há upload de arquivo, os dados de texto vêm em request.form e os arquivos em request.files
    legenda = request.form.get('legenda')
    tipo_midia = request.form.get('tipo_midia') 
    plataformas = request.form.get('plataformas') # Virá como string "instagram,whatsapp"
    data_agendamento_str = request.form.get('data_agendamento')

    if 'file' not in request.files:
        return jsonify({"message": "Nenhum arquivo enviado"}), 400
    
    file = request.files['file']

    if file.filename == '':
        return jsonify({"message": "Nome de arquivo vazio"}), 400

    # 2. Validação e Salvamento do Arquivo
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename) # Garante um nome de arquivo seguro
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        caminho_midia_para_db = file_path # Salvamos o caminho local no DB
    else:
        return jsonify({"message": "Tipo de arquivo não permitido"}), 400

    # 3. Validação dos Dados do Post
    if not all([legenda, tipo_midia, plataformas, data_agendamento_str]):
        # Se um arquivo foi salvo mas outros campos estão faltando, você pode querer deletá-lo
        # (Lógica mais complexa para um sistema de produção, mas para começar, está ok)
        os.remove(file_path) # Remove o arquivo se os dados do post estiverem incompletos
        return jsonify({"message": "Campos obrigatórios ausentes"}), 400

    try:
        data_agendamento = datetime.fromisoformat(data_agendamento_str)
    except ValueError:
        os.remove(file_path)
        return jsonify({"message": "Formato de data e hora inválido. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}), 400

    # 4. Inserção no Banco de Dados
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
        os.remove(file_path) # Remove o arquivo em caso de erro no DB
        print(f"Erro ao inserir post no banco: {e}")
        return jsonify({"message": "Erro ao criar post", "error": str(e)}), 500
    finally:
        connection.close()

@app.route('/posts', methods=['GET'])
def get_posts():
    """Endpoint para listar todos os posts."""
    connection = get_db_connection()
    if connection is None:
        return jsonify({"message": "Erro de conexão com o banco de dados"}), 500

    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM posts ORDER BY data_agendamento DESC"
            cursor.execute(sql)
            posts = cursor.fetchall()
            
            # Para cada post, adicione a URL completa da mídia
            # Isso é importante para o frontend poder exibir a imagem/vídeo
            for post in posts:
                if post['caminho_midia'] and os.path.exists(post['caminho_midia']):
                    # Flask serve arquivos estáticos de forma simples
                    post['url_midia'] = request.url_root + post['caminho_midia'] 
                else:
                    post['url_midia'] = None # Ou uma URL de placeholder
        return jsonify(posts), 200
    except Exception as e:
        print(f"Erro ao buscar posts no banco: {e}")
        return jsonify({"message": "Erro ao buscar posts", "error": str(e)}), 500
    finally:
        connection.close()

# Rota para servir arquivos estáticos (como as mídias uploaded)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# --- Execução do Servidor Flask ---
if __name__ == '__main__':
    # Quando for para produção, remova debug=True
    app.run(debug=True, port=5000)