import csv
import io
from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_required, current_user
from models import db, Usuario, PontoColeta, Descarte, Auditoria, Beneficio

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def is_gestor():
    return current_user.is_authenticated and current_user.papel in ("GESTOR", "ADMIN")


# ============= GESTÃO DE PONTOS DE COLETA =============
@admin_bp.route("/pontos")
@login_required
def admin_pontos():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))
    pontos = PontoColeta.query.order_by(PontoColeta.nome).all()
    return render_template("pontos_admin.html", pontos=pontos)


@admin_bp.route("/pontos/novo", methods=["GET", "POST"])
@login_required
def novo_ponto():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        ponto = PontoColeta(
            nome=request.form["nome"],
            endereco=request.form["endereco"],
            tipos_aceitos=request.form["tipos_aceitos"],
            horario_funcionamento=request.form.get("horario_funcionamento", ""),
            latitude=float(request.form["latitude"]) if request.form.get("latitude") else None,
            longitude=float(request.form["longitude"]) if request.form.get("longitude") else None
        )
        db.session.add(ponto)
        db.session.commit()
        flash("Ponto de coleta cadastrado com sucesso.", "success")
        return redirect(url_for("admin.admin_pontos"))

    return render_template("ponto_form.html", acao="Novo", ponto=None)


@admin_bp.route("/pontos/<int:ponto_id>/editar", methods=["GET", "POST"])
@login_required
def editar_ponto(ponto_id):
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    ponto = PontoColeta.query.get_or_404(ponto_id)

    if request.method == "POST":
        ponto.nome = request.form["nome"]
        ponto.endereco = request.form["endereco"]
        ponto.tipos_aceitos = request.form["tipos_aceitos"]
        ponto.horario_funcionamento = request.form.get("horario_funcionamento", "")
        ponto.latitude = float(request.form["latitude"]) if request.form.get("latitude") else None
        ponto.longitude = float(request.form["longitude"]) if request.form.get("longitude") else None
        db.session.commit()
        flash("Ponto de coleta atualizado com sucesso.", "success")
        return redirect(url_for("admin.admin_pontos"))

    return render_template("ponto_form.html", acao="Editar", ponto=ponto)


@admin_bp.route("/pontos/<int:ponto_id>/excluir", methods=["POST"])
@login_required
def excluir_ponto(ponto_id):
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    ponto = PontoColeta.query.get_or_404(ponto_id)
    db.session.delete(ponto)
    db.session.commit()
    flash("Ponto de coleta excluído com sucesso.", "info")
    return redirect(url_for("admin.admin_pontos"))


# ============= RELATÓRIOS DO GESTOR (com filtros e paginação) =============
@admin_bp.route("/relatorios")
@login_required
def relatorios_gestor():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    from datetime import datetime, timedelta

    # Filtros
    ponto_filtro = request.args.get("ponto_id", "", type=str)
    tipo_filtro = request.args.get("tipo", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 15

    query = Descarte.query

    if ponto_filtro:
        query = query.filter(Descarte.ponto_id == int(ponto_filtro))
    if tipo_filtro:
        query = query.filter(Descarte.tipo_residuo.ilike(f"%{tipo_filtro}%"))
    if data_inicio:
        try:
            query = query.filter(Descarte.data_hora >= datetime.strptime(data_inicio, "%Y-%m-%d"))
        except ValueError:
            pass
    if data_fim:
        try:
            query = query.filter(Descarte.data_hora < datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1))
        except ValueError:
            pass

    todos_descartes = query.all()
    total_descartes = len(todos_descartes)
    total_peso = sum(d.peso_kg for d in todos_descartes) if todos_descartes else 0
    total_pontos = sum(d.pontos_gerados for d in todos_descartes) if todos_descartes else 0

    estatistica_por_ponto = {}
    for d in todos_descartes:
        if d.ponto_id not in estatistica_por_ponto:
            estatistica_por_ponto[d.ponto_id] = {"peso_total": 0.0, "pontos_totais": 0, "qtd_descartes": 0}
        estatistica_por_ponto[d.ponto_id]["peso_total"] += d.peso_kg
        estatistica_por_ponto[d.ponto_id]["pontos_totais"] += d.pontos_gerados
        estatistica_por_ponto[d.ponto_id]["qtd_descartes"] += 1

    ranking_pontos = []
    for ponto_id, dados in estatistica_por_ponto.items():
        ponto = PontoColeta.query.get(ponto_id)
        ranking_pontos.append({
            "nome": ponto.nome if ponto else f"Ponto #{ponto_id}",
            "peso_total": dados["peso_total"],
            "pontos_totais": dados["pontos_totais"],
            "qtd_descartes": dados["qtd_descartes"],
        })
    ranking_pontos.sort(key=lambda x: x["qtd_descartes"], reverse=True)

    # Paginação dos descartes detalhados
    paginacao = (
        query.order_by(Descarte.data_hora.desc())
        .paginate(page=pagina, per_page=por_pagina, error_out=False)
    )

    # Dados para os filtros
    todos_pontos = PontoColeta.query.order_by(PontoColeta.nome).all()
    tipos_unicos = [
        t[0] for t in db.session.query(Descarte.tipo_residuo).distinct().all() if t[0]
    ]

    return render_template(
        "relatorios_gestor.html",
        total_descartes=total_descartes,
        total_peso=total_peso,
        total_pontos=total_pontos,
        ranking_pontos=ranking_pontos,
        paginacao=paginacao,
        todos_pontos=todos_pontos,
        tipos_unicos=tipos_unicos,
        ponto_filtro=ponto_filtro,
        tipo_filtro=tipo_filtro,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@admin_bp.route("/relatorios/exportar_csv")
@login_required
def exportar_relatorios_csv():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    descartes = Descarte.query.order_by(Descarte.data_hora.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Data/Hora", "Usuário (ID)", "Usuário (Nome)", "Usuário (E-mail)",
                     "Papel do Usuário", "Ponto de Coleta", "Tipo de Resíduo", "Peso (kg)", "Pontos Gerados"])

    for d in descartes:
        usuario = Usuario.query.get(d.usuario_id)
        ponto = PontoColeta.query.get(d.ponto_id)
        writer.writerow([
            d.data_hora.strftime("%Y-%m-%d %H:%M:%S"),
            d.usuario_id,
            usuario.nome if usuario else f"Usuário #{d.usuario_id}",
            usuario.email if usuario else "",
            usuario.papel if usuario else "",
            ponto.nome if ponto else f"Ponto #{d.ponto_id}",
            d.tipo_residuo,
            f"{d.peso_kg:.2f}",
            d.pontos_gerados,
        ])

    csv_data = output.getvalue()
    output.close()
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=relatorio_gestor_detalhado_ecosmart.csv"
    return response


@admin_bp.route("/relatorios/exportar_resumo_pontos_csv")
@login_required
def exportar_relatorios_resumo_pontos_csv():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    descartes = Descarte.query.all()
    estatistica_por_ponto = {}
    for d in descartes:
        if d.ponto_id not in estatistica_por_ponto:
            estatistica_por_ponto[d.ponto_id] = {"peso_total": 0.0, "pontos_totais": 0, "qtd_descartes": 0}
        estatistica_por_ponto[d.ponto_id]["peso_total"] += d.peso_kg
        estatistica_por_ponto[d.ponto_id]["pontos_totais"] += d.pontos_gerados
        estatistica_por_ponto[d.ponto_id]["qtd_descartes"] += 1

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Ponto de Coleta", "Quantidade de Descartes", "Peso Total (kg)", "Pontos Totais"])

    for ponto_id, dados in estatistica_por_ponto.items():
        ponto = PontoColeta.query.get(ponto_id)
        writer.writerow([
            ponto.nome if ponto else f"Ponto #{ponto_id}",
            dados["qtd_descartes"],
            f"{dados['peso_total']:.2f}",
            dados["pontos_totais"],
        ])

    csv_data = output.getvalue()
    output.close()
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=relatorio_gestor_resumo_pontos_ecosmart.csv"
    return response


# ============= ADMINISTRAÇÃO DO SISTEMA =============
@admin_bp.route("/usuarios")
@login_required
def admin_usuarios():
    if current_user.papel != "ADMIN":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("main.index"))
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return render_template("usuarios_admin.html", usuarios=usuarios)


@admin_bp.route("/usuarios/<int:user_id>/papel", methods=["POST"])
@login_required
def alterar_papel(user_id):
    if current_user.papel != "ADMIN":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("main.index"))

    novo_papel = request.form["papel"]
    usuario = Usuario.query.get_or_404(user_id)
    usuario.papel = novo_papel

    registro = Auditoria(
        usuario_id=current_user.id,
        acao=f"Alterou papel do usuário {usuario.email} para {novo_papel}"
    )
    db.session.add(registro)
    db.session.commit()

    flash("Papel atualizado!", "success")
    return redirect(url_for("admin.admin_usuarios"))


@admin_bp.route("/usuarios/<int:user_id>/status", methods=["POST"])
@login_required
def alterar_status_usuario(user_id):
    if current_user.papel != "ADMIN":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("main.index"))

    usuario = Usuario.query.get_or_404(user_id)
    usuario.ativo = not usuario.ativo
    acao = "Desativou" if not usuario.ativo else "Ativou"

    registro = Auditoria(
        usuario_id=current_user.id,
        acao=f"{acao} o usuário {usuario.email}"
    )
    db.session.add(registro)
    db.session.commit()

    flash("Status atualizado!", "success")
    return redirect(url_for("admin.admin_usuarios"))


@admin_bp.route("/auditoria")
@login_required
def admin_auditoria():
    if current_user.papel != "ADMIN":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("main.index"))
    registros = Auditoria.query.order_by(Auditoria.data.desc()).all()
    return render_template("auditoria.html", registros=registros)


# ============= GESTÃO DE BENEFÍCIOS (CRUD) =============
@admin_bp.route("/beneficios")
@login_required
def admin_beneficios():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))
    beneficios = Beneficio.query.order_by(Beneficio.nome).all()
    return render_template("beneficios_admin.html", beneficios=beneficios)


@admin_bp.route("/beneficios/novo", methods=["GET", "POST"])
@login_required
def novo_beneficio():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        beneficio = Beneficio(
            nome=request.form["nome"],
            descricao=request.form.get("descricao", ""),
            custo_pontos=int(request.form["custo_pontos"]),
            tipo=request.form.get("tipo", ""),
            ativo=True
        )
        db.session.add(beneficio)
        db.session.commit()
        flash("Benefício cadastrado com sucesso.", "success")
        return redirect(url_for("admin.admin_beneficios"))

    return render_template("beneficio_form.html", acao="Novo", beneficio=None)


@admin_bp.route("/beneficios/<int:beneficio_id>/editar", methods=["GET", "POST"])
@login_required
def editar_beneficio(beneficio_id):
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    beneficio = Beneficio.query.get_or_404(beneficio_id)

    if request.method == "POST":
        beneficio.nome = request.form["nome"]
        beneficio.descricao = request.form.get("descricao", "")
        beneficio.custo_pontos = int(request.form["custo_pontos"])
        beneficio.tipo = request.form.get("tipo", "")
        db.session.commit()
        flash("Benefício atualizado com sucesso.", "success")
        return redirect(url_for("admin.admin_beneficios"))

    return render_template("beneficio_form.html", acao="Editar", beneficio=beneficio)


@admin_bp.route("/beneficios/<int:beneficio_id>/toggle", methods=["POST"])
@login_required
def toggle_beneficio(beneficio_id):
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    beneficio = Beneficio.query.get_or_404(beneficio_id)
    beneficio.ativo = not beneficio.ativo
    db.session.commit()

    estado = "ativado" if beneficio.ativo else "desativado"
    flash(f"Benefício '{beneficio.nome}' {estado} com sucesso.", "success")
    return redirect(url_for("admin.admin_beneficios"))


@admin_bp.route("/beneficios/<int:beneficio_id>/excluir", methods=["POST"])
@login_required
def excluir_beneficio(beneficio_id):
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("main.index"))

    beneficio = Beneficio.query.get_or_404(beneficio_id)
    db.session.delete(beneficio)
    db.session.commit()
    flash("Benefício excluído com sucesso.", "info")
    return redirect(url_for("admin.admin_beneficios"))
