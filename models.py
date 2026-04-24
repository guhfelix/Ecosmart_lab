# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    papel = db.Column(db.String(20), default="CIDADAO")
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    saldo_pontos = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)  # usuário ativo/inativo


class PontoColeta(db.Model):
    __tablename__ = "pontos_coleta"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    tipos_aceitos = db.Column(db.String(255), nullable=False)
    horario_funcionamento = db.Column(db.String(120))

class Descarte(db.Model):
    __tablename__ = "descartes"

    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    tipo_residuo = db.Column(db.String(50), nullable=False)
    peso_kg = db.Column(db.Float, nullable=False)
    pontos_gerados = db.Column(db.Integer, nullable=False)

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    ponto_id = db.Column(db.Integer, db.ForeignKey("pontos_coleta.id"), nullable=False)

# ===== NOVO: Benefício =====
class Beneficio(db.Model):
    __tablename__ = "beneficios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    custo_pontos = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(50), nullable=True)  # ex.: DESCONTO, VOUCHER, ETC.
    ativo = db.Column(db.Boolean, default=True)

# ===== NOVO: Resgate =====
class Resgate(db.Model):
    __tablename__ = "resgates"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    beneficio_id = db.Column(db.Integer, db.ForeignKey("beneficios.id"), nullable=False)
    data_resgate = db.Column(db.DateTime, default=datetime.utcnow)
    pontos_utilizados = db.Column(db.Integer, nullable=False)
    codigo_voucher = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="ATIVO")  # ATIVO, USADO, EXPIRADO
    
class Auditoria(db.Model):
    __tablename__ = "auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    acao = db.Column(db.String(255), nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
