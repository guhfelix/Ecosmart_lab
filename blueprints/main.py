from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Descarte

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    descartes = (
        Descarte.query
        .filter_by(usuario_id=current_user.id)
        .order_by(Descarte.data_hora.desc())
        .all()
    )
    total_descartes = len(descartes)
    total_peso = sum(d.peso_kg for d in descartes) if descartes else 0
    ultimos_descartes = descartes[:5]
    return render_template(
        "dashboard.html",
        total_descartes=total_descartes,
        total_peso=total_peso,
        ultimos_descartes=ultimos_descartes,
    )
