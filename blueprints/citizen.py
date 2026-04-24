import csv
import io
import random
import string
from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_required, current_user
from models import db, PontoColeta, Descarte, Beneficio, Resgate

citizen_bp = Blueprint("citizen", __name__)


# ============= LISTAR PONTOS DE COLETA =============
@citizen_bp.route("/pontos")
@login_required
def pontos():
    lista_pontos = PontoColeta.query.all()
    return render_template("pontos.html", pontos=lista_pontos)


# ============= REGISTRAR DESCARTE =============
@citizen_bp.route("/descarte", methods=["GET", "POST"])
@login_required
def registrar_descarte():
    pontos = PontoColeta.query.all()

    if request.method == "POST":
        ponto_id = int(request.form["ponto_id"])
        tipo_residuo = request.form["tipo_residuo"]
        peso_kg = float(request.form["peso_kg"])

        pontos_gerados = int(peso_kg * 10)

        novo_descarte = Descarte(
            usuario_id=current_user.id,
            ponto_id=ponto_id,
            tipo_residuo=tipo_residuo,
            peso_kg=peso_kg,
            pontos_gerados=pontos_gerados,
        )

        current_user.saldo_pontos += pontos_gerados

        db.session.add(novo_descarte)
        db.session.commit()

        flash(f"Descarte registrado! Você ganhou {pontos_gerados} pontos.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("descarte.html", pontos=pontos)


# ============= RELATÓRIO PESSOAL (com filtros e paginação) =============
@citizen_bp.route("/relatorio")
@login_required
def relatorio_pessoal():
    # Parâmetros de filtro
    tipo_filtro = request.args.get("tipo", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 10

    query = Descarte.query.filter_by(usuario_id=current_user.id)

    if tipo_filtro:
        query = query.filter(Descarte.tipo_residuo.ilike(f"%{tipo_filtro}%"))

    if data_inicio:
        from datetime import datetime
        try:
            dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
            query = query.filter(Descarte.data_hora >= dt_inicio)
        except ValueError:
            pass

    if data_fim:
        from datetime import datetime
        try:
            dt_fim = datetime.strptime(data_fim, "%Y-%m-%d")
            # inclui o dia inteiro
            from datetime import timedelta
            query = query.filter(Descarte.data_hora < dt_fim + timedelta(days=1))
        except ValueError:
            pass

    # Totais sem paginação (sobre todos os descartes filtrados)
    todos_descartes = query.all()
    total_pontos = sum(d.pontos_gerados for d in todos_descartes)
    total_descartes = len(todos_descartes)
    total_peso = sum(d.peso_kg for d in todos_descartes) if todos_descartes else 0

    peso_por_tipo = {}
    for d in todos_descartes:
        tipo = d.tipo_residuo or "Não informado"
        peso_por_tipo[tipo] = peso_por_tipo.get(tipo, 0.0) + d.peso_kg

    labels_tipos = list(peso_por_tipo.keys())
    pesos_tipos = list(peso_por_tipo.values())

    # Paginação
    paginacao = (
        query.order_by(Descarte.data_hora.desc())
        .paginate(page=pagina, per_page=por_pagina, error_out=False)
    )

    # Tipos únicos para o filtro
    tipos_unicos = (
        db.session.query(Descarte.tipo_residuo)
        .filter_by(usuario_id=current_user.id)
        .distinct()
        .all()
    )
    tipos_unicos = [t[0] for t in tipos_unicos if t[0]]

    return render_template(
        "relatorio.html",
        descartes=paginacao.items,
        paginacao=paginacao,
        total_pontos=total_pontos,
        total_descartes=total_descartes,
        total_peso=total_peso,
        labels_tipos=labels_tipos,
        pesos_tipos=pesos_tipos,
        tipo_filtro=tipo_filtro,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipos_unicos=tipos_unicos,
    )


# ============= EXPORTAR RELATÓRIO PESSOAL EM CSV =============
@citizen_bp.route("/relatorio/exportar_csv")
@login_required
def exportar_relatorio_csv():
    descartes = (
        Descarte.query
        .filter_by(usuario_id=current_user.id)
        .order_by(Descarte.data_hora.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Data/Hora", "Ponto de Coleta", "Tipo de Resíduo", "Peso (kg)", "Pontos Gerados"])

    for d in descartes:
        ponto = PontoColeta.query.get(d.ponto_id)
        nome_ponto = ponto.nome if ponto else f"Ponto #{d.ponto_id}"
        writer.writerow([
            d.data_hora.strftime("%Y-%m-%d %H:%M:%S"),
            nome_ponto,
            d.tipo_residuo,
            f"{d.peso_kg:.2f}",
            d.pontos_gerados,
        ])

    csv_data = output.getvalue()
    output.close()

    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=relatorio_pessoal_ecosmart.csv"
    return response


# ============= RESGATAR BENEFÍCIOS =============
@citizen_bp.route("/beneficios", methods=["GET", "POST"])
@login_required
def beneficios():
    lista_beneficios = Beneficio.query.filter_by(ativo=True).all()

    if request.method == "POST":
        beneficio_id = int(request.form["beneficio_id"])
        beneficio = Beneficio.query.get_or_404(beneficio_id)

        if current_user.saldo_pontos < beneficio.custo_pontos:
            flash("Saldo de pontos insuficiente para este benefício.", "danger")
            return redirect(url_for("citizen.beneficios"))

        current_user.saldo_pontos -= beneficio.custo_pontos

        codigo = "ECO-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

        novo_resgate = Resgate(
            usuario_id=current_user.id,
            beneficio_id=beneficio.id,
            pontos_utilizados=beneficio.custo_pontos,
            codigo_voucher=codigo,
            status="ATIVO"
        )

        db.session.add(novo_resgate)
        db.session.commit()

        flash(f"Benefício '{beneficio.nome}' resgatado com sucesso! Código: {codigo}", "success")
        return redirect(url_for("citizen.meus_resgates"))

    return render_template("beneficios.html", beneficios=lista_beneficios)


# ============= HISTÓRICO DE RESGATES =============
@citizen_bp.route("/meus-resgates")
@login_required
def meus_resgates():
    resgates = (
        Resgate.query
        .filter_by(usuario_id=current_user.id)
        .order_by(Resgate.data_resgate.desc())
        .all()
    )

    # Enriquece com o nome do benefício
    resgates_detalhados = []
    for r in resgates:
        beneficio = Beneficio.query.get(r.beneficio_id)
        resgates_detalhados.append({
            "id": r.id,
            "data_resgate": r.data_resgate,
            "nome_beneficio": beneficio.nome if beneficio else f"Benefício #{r.beneficio_id}",
            "tipo_beneficio": beneficio.tipo if beneficio else "—",
            "pontos_utilizados": r.pontos_utilizados,
            "codigo_voucher": r.codigo_voucher,
            "status": r.status,
        })

    total_pontos_gastos = sum(r["pontos_utilizados"] for r in resgates_detalhados)

    return render_template(
        "meus_resgates.html",
        resgates=resgates_detalhados,
        total_pontos_gastos=total_pontos_gastos,
    )
