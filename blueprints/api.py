from flask import Blueprint, jsonify
from models import db, PontoColeta, Beneficio, Descarte
from sqlalchemy import func

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

@api_bp.route("/pontos")
def get_pontos():
    pontos = PontoColeta.query.all()
    return jsonify([{
        "id": p.id,
        "nome": p.nome,
        "endereco": p.endereco,
        "tipos_aceitos": p.tipos_aceitos,
        "horario": p.horario_funcionamento,
        "latitude": p.latitude,
        "longitude": p.longitude
    } for p in pontos])

@api_bp.route("/beneficios")
def get_beneficios():
    beneficios = Beneficio.query.filter_by(ativo=True).all()
    return jsonify([{
        "id": b.id,
        "nome": b.nome,
        "descricao": b.descricao,
        "custo_pontos": b.custo_pontos,
        "tipo": b.tipo
    } for b in beneficios])

@api_bp.route("/estatisticas")
def get_estatisticas():
    total_descartes = Descarte.query.count()
    total_peso = db.session.query(func.sum(Descarte.peso_kg)).scalar() or 0
    total_pontos = db.session.query(func.sum(Descarte.pontos_gerados)).scalar() or 0
    
    # Peso por tipo
    resumo_tipos = db.session.query(
        Descarte.tipo_residuo, 
        func.sum(Descarte.peso_kg).label("peso_total")
    ).group_by(Descarte.tipo_residuo).all()

    return jsonify({
        "geral": {
            "total_descartes": total_descartes,
            "total_peso_kg": float(total_peso),
            "total_pontos_gerados": int(total_pontos)
        },
        "por_tipo": {t[0]: float(t[1]) for t in resumo_tipos if t[0]}
    })
