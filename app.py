# app.py

from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

# Importar load_dotenv
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Adicione uma variável de configuração para a URL base do seu backend
# Você pode pegar isso de uma variável de ambiente ou definir diretamente para desenvolvimento.
# Para produção, você usaria o domínio real do seu backend (ex: https://api.meusite.com)
BACKEND_BASE_URL = os.getenv('BACKEND_URL', 'http://localhost:5000') # Defina a porta do seu Flask aqui

# --- Configuração do Banco de Dados MySQL usando variáveis de ambiente ---
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_PORT = os.getenv('MYSQL_PORT')
MYSQL_DB = os.getenv('MYSQL_DB')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração da pasta de uploads para posts e produtos
UPLOAD_FOLDER_POSTS = 'uploads/posts'
UPLOAD_FOLDER_PRODUCTS = 'uploads/products'
app.config['UPLOAD_FOLDER_POSTS'] = UPLOAD_FOLDER_POSTS
app.config['UPLOAD_FOLDER_PRODUCTS'] = UPLOAD_FOLDER_PRODUCTS

os.makedirs(UPLOAD_FOLDER_POSTS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_PRODUCTS, exist_ok=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Funções auxiliares para manipulação de arquivos
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file, upload_folder):
    if file and allowed_file(file.filename):
        filename_base = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename_base}"
        filepath = os.path.join(upload_folder, unique_filename) # Caminho real no disco
        file.save(filepath)
        
        # ALTERAÇÃO AQUI: Garante que o caminho para o DB e URL use sempre '/'
        # os.path.basename(upload_folder) pega 'posts' ou 'products'
        return f"{os.path.basename(upload_folder)}/{unique_filename}" 
    return None

def delete_file(filepath_relative):
    # ATENÇÃO: Se o filepath_relative agora virá com '/', o os.sep não funcionará diretamente para split.
    # Você precisará usar o '/' como separador para split e join para apagar.
    # O folder_name deve ser o primeiro elemento da string 'posts/nome_arquivo.png'
    # O nome do arquivo real será o segundo elemento.
    
    # Ex: filepath_relative = 'products/5a9c0bcef5bf707474128f309e307e2_7047.png'
    # folder_name = 'products'
    # filename_only = '5a9c0bcef5bf707474128f309e307e2_7047.png'
    
    if filepath_relative:
        parts = filepath_relative.split('/') # Usa '/' como separador, já que agora salvamos assim
        if len(parts) < 2: # Garante que há pelo menos 'folder/filename'
            return False # Caminho inválido para exclusão

        folder_name = parts[0] # 'posts' ou 'products'
        filename_only = parts[1] # 'nome_do_arquivo.ext'
        
        full_path = None
        if folder_name == 'posts':
            full_path = os.path.join(app.config['UPLOAD_FOLDER_POSTS'], filename_only)
        elif folder_name == 'products':
            full_path = os.path.join(app.config['UPLOAD_FOLDER_PRODUCTS'], filename_only)
        
        if full_path and os.path.exists(full_path):
            os.remove(full_path)
            return True
    return False

# --- Modelos de Banco de Dados ---

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    legenda = db.Column(db.Text, nullable=False)
    tipo_midia = db.Column(db.String(50), nullable=False)
    url_midia = db.Column(db.String(255), nullable=True)
    plataformas = db.Column(db.String(255), nullable=False)
    data_agendamento = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), default='agendado')
    data_publicacao = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'legenda': self.legenda,
            'tipo_midia': self.tipo_midia,
            # Se a url_midia já é uma URL completa (ex: de uma API externa), não a modifique.
            # Caso contrário, construa a URL completa baseada no caminho relativo salvo.
            'url_midia': self.get_full_media_url(self.url_midia) if self.url_midia and not self.url_midia.startswith('http') else self.url_midia,
            'plataformas': self.plataformas,
            'data_agendamento': self.data_agendamento.isoformat(),
            'status': self.status,
            'data_publicacao': self.data_publicacao.isoformat() if self.data_publicacao else None
        }
    
    def get_full_media_url(self, relative_path):
        # ALTERAÇÃO AQUI: Simplificação, já que relative_path deve vir formatado com '/'
        # E a rota `/uploads/<path:filename>` espera o caminho relativo completo (ex: 'posts/imagem.png')
        if relative_path:
            return f'{BACKEND_BASE_URL}/uploads/{relative_path}'
        return None # Ou um placeholder para imagem/video faltando

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    age_classification = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    media = db.relationship('ProductMedia', backref='product', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'age_classification': self.age_classification,
            'price': self.price,
            'quantity': self.quantity,
            'media': [m.to_dict() for m in self.media]
        }

class ProductMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    url_midia = db.Column(db.String(255), nullable=False)
    tipo_midia = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'url_midia': self.get_full_media_url(self.url_midia),
            'tipo_midia': self.tipo_midia,
            'filename': self.filename
        }
    
    def get_full_media_url(self, relative_path):
        # Este método já estava correto para o retorno esperado (ex: '/uploads/products/imagem.png')
        if relative_path:
            return f'{BACKEND_BASE_URL}/uploads/{relative_path}'
        return None # Ou um placeholder para imagem/video faltando

# --- Rotas para servir arquivos estáticos de uploads ---
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # O 'filename' aqui já virá como 'posts/nome.png' ou 'products/nome.png'
    # Os send_from_directory precisam apenas do 'nome.png' e da pasta base 'uploads/posts' ou 'uploads/products'
    if filename.startswith('posts/'):
        return send_from_directory(app.config['UPLOAD_FOLDER_POSTS'], filename.replace('posts/', ''))
    elif filename.startswith('products/'):
        return send_from_directory(app.config['UPLOAD_FOLDER_PRODUCTS'], filename.replace('products/', ''))
    return jsonify({"message": "File not found"}), 404

# --- Rotas da API para Posts ---

@app.route('/posts', methods=['GET'])
def get_posts():
    posts = Post.query.all()
    return jsonify([post.to_dict() for post in posts])

@app.route('/posts/<int:id>', methods=['GET'])
def get_post(id):
    post = Post.query.get_or_404(id)
    return jsonify(post.to_dict())

@app.route('/posts', methods=['POST'])
def create_post():
    legenda = request.form.get('legenda')
    tipo_midia = request.form.get('tipo_midia')
    plataformas = request.form.getlist('plataformas')
    data_agendamento_str = request.form.get('data_agendamento')

    if not all([legenda, tipo_midia, plataformas, data_agendamento_str]):
        return jsonify({"message": "Dados obrigatórios faltando"}), 400

    try:
        data_agendamento = datetime.fromisoformat(data_agendamento_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"message": "Formato de data e hora inválido"}), 400

    url_midia = None
    if 'media_file' in request.files:
        file = request.files['media_file']
        if file.filename != '':
            relative_filepath = save_file(file, app.config['UPLOAD_FOLDER_POSTS'])
            if relative_filepath:
                url_midia = relative_filepath 
            else:
                return jsonify({"message": "Tipo de arquivo de mídia não permitido"}), 400
    elif request.form.get('url_midia'):
        url_midia = request.form.get('url_midia')

    new_post = Post(
        legenda=legenda,
        tipo_midia=tipo_midia,
        url_midia=url_midia,
        plataformas=','.join(plataformas),
        data_agendamento=data_agendamento,
        status='agendado'
    )
    db.session.add(new_post)
    db.session.commit()
    return jsonify(new_post.to_dict()), 201

@app.route('/posts/<int:id>', methods=['PUT'])
def update_post(id):
    post = Post.query.get_or_404(id)

    legenda = request.form.get('legenda')
    tipo_midia = request.form.get('tipo_midia')
    plataformas = request.form.getlist('plataformas')
    data_agendamento_str = request.form.get('data_agendamento')

    if not all([legenda, tipo_midia, plataformas, data_agendamento_str]):
        return jsonify({"message": "Dados obrigatórios faltando"}), 400

    try:
        data_agendamento = datetime.fromisoformat(data_agendamento_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"message": "Formato de data e hora inválido"}), 400

    new_url_midia_form = request.form.get('url_midia')
    existing_url_midia = post.url_midia

    if 'media_file' in request.files and request.files['media_file'].filename != '':
        file = request.files['media_file']
        if existing_url_midia and not existing_url_midia.startswith('http'):
            delete_file(existing_url_midia)
        
        relative_filepath = save_file(file, app.config['UPLOAD_FOLDER_POSTS'])
        if relative_filepath:
            post.url_midia = relative_filepath
        else:
            return jsonify({"message": "Tipo de arquivo de mídia não permitido"}), 400
    elif new_url_midia_form == '':
        if existing_url_midia and not existing_url_midia.startswith('http'):
            delete_file(existing_url_midia)
        post.url_midia = None
    elif new_url_midia_form and new_url_midia_form != existing_url_midia:
        if existing_url_midia and not existing_url_midia.startswith('http') and existing_url_midia != new_url_midia_form:
            delete_file(existing_url_midia)
        post.url_midia = new_url_midia_form

    post.legenda = legenda
    post.tipo_midia = tipo_midia
    post.plataformas = ','.join(plataformas)
    post.data_agendamento = data_agendamento

    db.session.commit()
    return jsonify(post.to_dict())

@app.route('/posts/<int:id>', methods=['DELETE'])
def delete_post(id):
    post = Post.query.get_or_404(id)
    if post.url_midia and not post.url_midia.startswith('http'):
        delete_file(post.url_midia)
    db.session.delete(post)
    db.session.commit()
    return jsonify({"message": "Post excluído com sucesso"})

# --- Rotas da API para Produtos ---

@app.route('/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([p.to_dict() for p in products])

@app.route('/products/<int:id>', methods=['GET'])
def get_product(id):
    product = Product.query.get_or_404(id)
    return jsonify(product.to_dict())

@app.route('/products', methods=['POST'])
def create_product():
    name = request.form.get('name')
    description = request.form.get('description', None)
    age_classification = request.form.get('age_classification')
    price = request.form.get('price')
    quantity = request.form.get('quantity')

    if not all([name, age_classification, price is not None, quantity is not None]):
        return jsonify({"message": "Dados obrigatórios faltando"}), 400

    try:
        price = float(price)
        quantity = int(quantity)
    except ValueError:
        return jsonify({"message": "Preço ou quantidade inválidos"}), 400

    new_product = Product(
        name=name,
        description=description,
        age_classification=age_classification,
        price=price,
        quantity=quantity
    )
    db.session.add(new_product)
    db.session.commit()

    if 'media_files' in request.files:
        files = request.files.getlist('media_files')
        for file in files:
            if file.filename == '':
                continue
            relative_filepath = save_file(file, app.config['UPLOAD_FOLDER_PRODUCTS'])
            if relative_filepath:
                new_media = ProductMedia(
                    product_id=new_product.id,
                    url_midia=relative_filepath,
                    tipo_midia='imagem' if file.mimetype.startswith('image/') else 'video',
                    filename=secure_filename(file.filename)
                )
                db.session.add(new_media)
            else:
                print(f"Tipo de arquivo não permitido para: {file.filename}")
    db.session.commit()
    return jsonify(new_product.to_dict()), 201

@app.route('/products/<int:id>', methods=['PUT'])
def update_product(id):
    product = Product.query.get_or_404(id)

    name = request.form.get('name', product.name)
    description = request.form.get('description', product.description)
    age_classification = request.form.get('age_classification', product.age_classification)
    price_str = request.form.get('price', str(product.price))
    quantity_str = request.form.get('quantity', str(product.quantity))

    try:
        price = float(price_str)
        quantity = int(quantity_str)
    except ValueError:
        return jsonify({"message": "Preço ou quantidade inválidos"}), 400

    product.name = name
    product.description = description
    product.age_classification = age_classification
    product.price = price
    product.quantity = quantity

    if 'media_files' in request.files:
        files = request.files.getlist('media_files')
        for file in files:
            if file.filename == '':
                continue
            relative_filepath = save_file(file, app.config['UPLOAD_FOLDER_PRODUCTS'])
            if relative_filepath:
                new_media = ProductMedia(
                    product_id=product.id,
                    url_midia=relative_filepath,
                    tipo_midia='imagem' if file.mimetype.startswith('image/') else 'video',
                    filename=secure_filename(file.filename)
                )
                db.session.add(new_media)
            else:
                print(f"Tipo de arquivo não permitido para: {file.filename}")

    db.session.commit()
    return jsonify(product.to_dict())

@app.route('/products/<int:product_id>/media/<int:media_id>', methods=['DELETE'])
def delete_product_media(product_id, media_id):
    media = ProductMedia.query.filter_by(id=media_id, product_id=product_id).first_or_404()
    
    if media.url_midia:
        delete_file(media.url_midia)
    
    db.session.delete(media)
    db.session.commit()
    return jsonify({"message": "Mídia do produto excluída com sucesso"}), 200

@app.route('/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    product = Product.query.get_or_404(id)
    for media_item in product.media:
        delete_file(media_item.url_midia)

    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Produto e suas mídias excluídos com sucesso"}), 200

if __name__ == '__main__':
    with app.app_context():
        pass # Migrações cuidam da criação das tabelas

    app.run(debug=True)