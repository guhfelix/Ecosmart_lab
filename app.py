import os
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, Usuario, PontoColeta, Beneficio
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env (se existir)
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-padrao-apenas-para-dev")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URI", "sqlite:///ecosmart.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Extensões
db.init_app(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)

# Login Manager
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ============= REGISTRAR BLUEPRINTS =============
from blueprints.main import main_bp
from blueprints.auth import auth_bp
from blueprints.citizen import citizen_bp
from blueprints.admin import admin_bp
from blueprints.api import api_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(citizen_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Isentar a API de proteção CSRF (padrão para APIs REST que usam outros métodos de auth)
csrf.exempt(api_bp)


# ============= INICIALIZAÇÃO DO BANCO DE DADOS =============
with app.app_context():
    db.create_all()

    # Dados iniciais: Pontos de Coleta
    if PontoColeta.query.count() == 0:
        pontos_iniciais = [
            PontoColeta(
                nome="Ponto Central",
                endereco="Praça Central, 123",
                tipos_aceitos="Plástico, Vidro, Papel, Metal",
                horario_funcionamento="08h às 17h"
            ),
            PontoColeta(
                nome="EcoPonto Bairro Verde",
                endereco="Av. das Árvores, 456",
                tipos_aceitos="Eletrônicos, Pilhas, Baterias",
                horario_funcionamento="09h às 18h"
            ),
            PontoColeta(
                nome="Coleta Municipal",
                endereco="Rua da Prefeitura, 789",
                tipos_aceitos="Vidro, Metal",
                horario_funcionamento="07h às 16h"
            ),
        ]
        db.session.add_all(pontos_iniciais)
        db.session.commit()

    # Dados iniciais: Benefícios
    if Beneficio.query.count() == 0:
        beneficios_iniciais = [
            Beneficio(
                nome="Desconto na Conta de Água",
                descricao="R$ 20,00 de desconto na próxima fatura de água.",
                custo_pontos=100,
                tipo="DESCONTO"
            ),
            Beneficio(
                nome="Desconto na Conta de Luz",
                descricao="R$ 15,00 de desconto na fatura de energia.",
                custo_pontos=80,
                tipo="DESCONTO"
            ),
            Beneficio(
                nome="Voucher em Loja Parceira",
                descricao="Voucher de R$ 30,00 para compras em parceira local.",
                custo_pontos=150,
                tipo="VOUCHER"
            ),
        ]
        db.session.add_all(beneficios_iniciais)
        db.session.commit()


# ============= START =============
if __name__ == "__main__":
    app.run(debug=True)
