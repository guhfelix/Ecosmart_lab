from flask import Flask, render_template, redirect, url_for, request, flash, make_response
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Usuario, PontoColeta, Descarte, Beneficio, Resgate, Auditoria
import csv
import io


app = Flask(__name__)
app.config["SECRET_KEY"] = "chave-secreta-aqui"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ecosmart.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
bcrypt = Bcrypt(app)

# Login Manager
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Criar tabelas (Flask 3+)
with app.app_context():
    db.create_all()

# ============= HOME =============
@app.route("/")
def index():
    return render_template("index.html")

# ============= CADASTRO =============
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash("E-mail já cadastrado!", "danger")
            return redirect(url_for("register"))

        senha_hash = bcrypt.generate_password_hash(senha).decode("utf-8")
        usuario = Usuario(nome=nome, email=email, senha_hash=senha_hash)

        db.session.add(usuario)
        db.session.commit()

        flash("Cadastro realizado! Agora faça login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# ============= LOGIN =============
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and bcrypt.check_password_hash(usuario.senha_hash, senha):
            login_user(usuario)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("index"))

        flash("E-mail ou senha inválidos.", "danger")

    return render_template("login.html")

# ============= LOGOUT =============
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("index"))

# ============= LISTAR PONTOS DE COLETA =============
@app.route("/pontos")
@login_required
def pontos():
    lista_pontos = PontoColeta.query.all()
    return render_template("pontos.html", pontos=lista_pontos)

# --- Adicionar pontos de coleta iniciais ---
with app.app_context():
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

# ============= REGISTRAR DESCARTE (UC05) =============
@app.route("/descarte", methods=["GET", "POST"])
@login_required
def registrar_descarte():
    pontos = PontoColeta.query.all()  # para preencher o select

    if request.method == "POST":
        ponto_id = int(request.form["ponto_id"])
        tipo_residuo = request.form["tipo_residuo"]
        peso_kg = float(request.form["peso_kg"])

        # regra simples: 10 pontos por kg
        pontos_gerados = int(peso_kg * 10)

        novo_descarte = Descarte(
            usuario_id=current_user.id,
            ponto_id=ponto_id,
            tipo_residuo=tipo_residuo,
            peso_kg=peso_kg,
            pontos_gerados=pontos_gerados,
        )

        # atualiza saldo do usuário
        current_user.saldo_pontos += pontos_gerados

        db.session.add(novo_descarte)
        db.session.commit()

        flash(f"Descarte registrado! Você ganhou {pontos_gerados} pontos.", "success")
        return redirect(url_for("index"))  # depois a gente pode mandar pra um relatório

    return render_template("descarte.html", pontos=pontos)

# ============= RELATÓRIO PESSOAL (UC08) =============
@app.route("/relatorio")
@login_required
def relatorio_pessoal():
    descartes = (
        Descarte.query
        .filter_by(usuario_id=current_user.id)
        .order_by(Descarte.data_hora.desc())
        .all()
    )

    total_pontos = sum(d.pontos_gerados for d in descartes)
    total_descartes = len(descartes)
    total_peso = sum(d.peso_kg for d in descartes) if descartes else 0

    peso_por_tipo = {}
    for d in descartes:
        tipo = d.tipo_residuo or "Não informado"
        if tipo not in peso_por_tipo:
            peso_por_tipo[tipo] = 0.0
        peso_por_tipo[tipo] += d.peso_kg

    labels_tipos = list(peso_por_tipo.keys())
    pesos_tipos = list(peso_por_tipo.values())

    return render_template(
        "relatorio.html",
        descartes=descartes,
        total_pontos=total_pontos,
        total_descartes=total_descartes,
        total_peso=total_peso,
        labels_tipos=labels_tipos,
        pesos_tipos=pesos_tipos,
    )

# ============= EXPORTAR RELATÓRIO PESSOAL EM CSV (UC08) =============
@app.route("/relatorio/exportar_csv")
@login_required
def exportar_relatorio_csv():
    # pega apenas os descartes do usuário logado
    descartes = (
        Descarte.query
        .filter_by(usuario_id=current_user.id)
        .order_by(Descarte.data_hora.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Cabeçalho
    writer.writerow([
        "Data/Hora",
        "Ponto de Coleta",
        "Tipo de Resíduo",
        "Peso (kg)",
        "Pontos Gerados",
    ])

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

# ============= RESGATAR BENEFÍCIOS (UC06) =============
@app.route("/beneficios", methods=["GET", "POST"])
@login_required
def beneficios():
    beneficios = Beneficio.query.filter_by(ativo=True).all()

    if request.method == "POST":
        beneficio_id = int(request.form["beneficio_id"])
        beneficio = Beneficio.query.get_or_404(beneficio_id)

        # verificar saldo
        if current_user.saldo_pontos < beneficio.custo_pontos:
            flash("Saldo de pontos insuficiente para este benefício.", "danger")
            return redirect(url_for("beneficios"))

        # debitar pontos
        current_user.saldo_pontos -= beneficio.custo_pontos

        # gerar “código de voucher” simples (poderia ser mais robusto)
        import random, string
        codigo = "ECO-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # registrar resgate
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
        return redirect(url_for("beneficios"))

    return render_template("beneficios.html", beneficios=beneficios)

# --- Adicionar benefícios iniciais ---
with app.app_context():
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

# ------------ Helper para verificar se é gestor ------------
def is_gestor():
    return current_user.is_authenticated and current_user.papel in ("GESTOR", "ADMIN")

# ============= GESTÃO DE PONTOS DE COLETA (UC09) =============

@app.route("/admin/pontos")
@login_required
def admin_pontos():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("index"))

    pontos = PontoColeta.query.order_by(PontoColeta.nome).all()
    return render_template("pontos_admin.html", pontos=pontos)

@app.route("/admin/pontos/novo", methods=["GET", "POST"])
@login_required
def novo_ponto():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        nome = request.form["nome"]
        endereco = request.form["endereco"]
        tipos_aceitos = request.form["tipos_aceitos"]
        horario = request.form["horario_funcionamento"]

        ponto = PontoColeta(
            nome=nome,
            endereco=endereco,
            tipos_aceitos=tipos_aceitos,
            horario_funcionamento=horario
        )
        db.session.add(ponto)
        db.session.commit()

        flash("Ponto de coleta cadastrado com sucesso.", "success")
        return redirect(url_for("admin_pontos"))

    return render_template("ponto_form.html", acao="Novo", ponto=None)

@app.route("/admin/pontos/<int:ponto_id>/editar", methods=["GET", "POST"])
@login_required
def editar_ponto(ponto_id):
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("index"))

    ponto = PontoColeta.query.get_or_404(ponto_id)

    if request.method == "POST":
        ponto.nome = request.form["nome"]
        ponto.endereco = request.form["endereco"]
        ponto.tipos_aceitos = request.form["tipos_aceitos"]
        ponto.horario_funcionamento = request.form["horario_funcionamento"]

        db.session.commit()
        flash("Ponto de coleta atualizado com sucesso.", "success")
        return redirect(url_for("admin_pontos"))

    return render_template("ponto_form.html", acao="Editar", ponto=ponto)

@app.route("/admin/pontos/<int:ponto_id>/excluir", methods=["POST"])
@login_required
def excluir_ponto(ponto_id):
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("index"))

    ponto = PontoColeta.query.get_or_404(ponto_id)
    db.session.delete(ponto)
    db.session.commit()

    flash("Ponto de coleta excluído com sucesso.", "info")
    return redirect(url_for("admin_pontos"))

# ======== ROTA TEMPORÁRIA: listar usuários (para ver ID) ========
@app.route("/listar_usuarios")
def listar_usuarios():
    usuarios = Usuario.query.all()
    texto = []
    for u in usuarios:
        texto.append(f"ID: {u.id} | Nome: {u.nome} | Email: {u.email} | Papel: {u.papel}")
    return "<br>".join(texto)

# ======== ROTA TEMPORÁRIA: tornar um usuário GESTOR ========
@app.route("/tornar_gestor/<int:user_id>")
def tornar_gestor(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        return f"Usuário com ID {user_id} não encontrado."

    usuario.papel = "GESTOR"
    db.session.commit()
    return f"Usuário {usuario.nome} (ID {usuario.id}) agora é GESTOR!"

# ============= RELATÓRIOS DO GESTOR (UC11) =============
@app.route("/admin/relatorios")
@login_required
def relatorios_gestor():
    if not is_gestor():  # GESTOR ou ADMIN
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("index"))

    descartes = Descarte.query.all()

    total_descartes = len(descartes)
    total_peso = sum(d.peso_kg for d in descartes) if descartes else 0
    total_pontos = sum(d.pontos_gerados for d in descartes) if descartes else 0

    # agregando por ponto de coleta
    estatistica_por_ponto = {}
    for d in descartes:
        if d.ponto_id not in estatistica_por_ponto:
            estatistica_por_ponto[d.ponto_id] = {
                "peso_total": 0.0,
                "pontos_totais": 0,
                "qtd_descartes": 0,
            }
        estatistica_por_ponto[d.ponto_id]["peso_total"] += d.peso_kg
        estatistica_por_ponto[d.ponto_id]["pontos_totais"] += d.pontos_gerados
        estatistica_por_ponto[d.ponto_id]["qtd_descartes"] += 1

    # transformar em lista com nome do ponto
    ranking_pontos = []
    for ponto_id, dados in estatistica_por_ponto.items():
        ponto = PontoColeta.query.get(ponto_id)
        ranking_pontos.append({
            "nome": ponto.nome if ponto else f"Ponto #{ponto_id}",
            "peso_total": dados["peso_total"],
            "pontos_totais": dados["pontos_totais"],
            "qtd_descartes": dados["qtd_descartes"],
        })

    # ordenar do que mais recebeu descartes pro que menos
    ranking_pontos.sort(key=lambda x: x["qtd_descartes"], reverse=True)

    return render_template(
        "relatorios_gestor.html",
        total_descartes=total_descartes,
        total_peso=total_peso,
        total_pontos=total_pontos,
        ranking_pontos=ranking_pontos,
    )


# ======== ADIMINISTRAÇÃO DO SISTEMA UC12 ========
@app.route("/admin/usuarios")
@login_required
def admin_usuarios():
    if current_user.papel != "ADMIN":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("index"))

    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return render_template("usuarios_admin.html", usuarios=usuarios)

@app.route("/admin/usuarios/<int:user_id>/papel", methods=["POST"])
@login_required
def alterar_papel(user_id):
    if current_user.papel != "ADMIN":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("index"))

    novo_papel = request.form["papel"]
    usuario = Usuario.query.get_or_404(user_id)

    usuario.papel = novo_papel

    # registrar auditoria
    registro = Auditoria(
        usuario_id=current_user.id,
        acao=f"Alterou papel do usuário {usuario.email} para {novo_papel}"
    )

    db.session.add(registro)
    db.session.commit()

    flash("Papel atualizado!", "success")
    return redirect(url_for("admin_usuarios"))

@app.route("/admin/usuarios/<int:user_id>/status", methods=["POST"])
@login_required
def alterar_status_usuario(user_id):
    if current_user.papel != "ADMIN":
        flash("Acesso restrito.", "danger")
        return redirect(url_for("index"))

    usuario = Usuario.query.get_or_404(user_id)
    usuario.ativo = not usuario.ativo

    acao = "Desativou" if usuario.ativo is False else "Ativou"

    registro = Auditoria(
        usuario_id=current_user.id,
        acao=f"{acao} o usuário {usuario.email}"
    )

    db.session.add(registro)
    db.session.commit()

    flash("Status atualizado!", "success")
    return redirect(url_for("admin_usuarios"))

@app.route("/admin/auditoria")
@login_required
def admin_auditoria():
    if current_user.papel != "ADMIN":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("index"))

    registros = Auditoria.query.order_by(Auditoria.data.desc()).all()
    return render_template("auditoria.html", registros=registros)

# ============= EXPORTAR RELATÓRIOS DO GESTOR – DETALHADO =============
@app.route("/admin/relatorios/exportar_csv")
@login_required
def exportar_relatorios_csv():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("index"))

    descartes = (
        Descarte.query
        .order_by(Descarte.data_hora.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Cabeçalho detalhado
    writer.writerow([
        "Data/Hora",
        "Usuário (ID)",
        "Usuário (Nome)",
        "Usuário (E-mail)",
        "Papel do Usuário",
        "Ponto de Coleta",
        "Tipo de Resíduo",
        "Peso (kg)",
        "Pontos Gerados",
    ])

    for d in descartes:
        usuario = Usuario.query.get(d.usuario_id)
        ponto = PontoColeta.query.get(d.ponto_id)

        nome_usuario = usuario.nome if usuario else f"Usuário #{d.usuario_id}"
        email_usuario = usuario.email if usuario else ""
        papel_usuario = usuario.papel if usuario else ""
        nome_ponto = ponto.nome if ponto else f"Ponto #{d.ponto_id}"

        writer.writerow([
            d.data_hora.strftime("%Y-%m-%d %H:%M:%S"),
            d.usuario_id,
            nome_usuario,
            email_usuario,
            papel_usuario,
            nome_ponto,
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

# ============= EXPORTAR RESUMO POR PONTO DE COLETA (AGREGADO) =============
@app.route("/admin/relatorios/exportar_resumo_pontos_csv")
@login_required
def exportar_relatorios_resumo_pontos_csv():
    if not is_gestor():
        flash("Acesso restrito a gestores municipais.", "danger")
        return redirect(url_for("index"))

    descartes = Descarte.query.all()

    # Agrupa por ponto de coleta
    estatistica_por_ponto = {}
    for d in descartes:
        if d.ponto_id not in estatistica_por_ponto:
            estatistica_por_ponto[d.ponto_id] = {
                "peso_total": 0.0,
                "pontos_totais": 0,
                "qtd_descartes": 0,
            }
        estatistica_por_ponto[d.ponto_id]["peso_total"] += d.peso_kg
        estatistica_por_ponto[d.ponto_id]["pontos_totais"] += d.pontos_gerados
        estatistica_por_ponto[d.ponto_id]["qtd_descartes"] += 1

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Cabeçalho do resumo
    writer.writerow([
        "Ponto de Coleta",
        "Quantidade de Descartes",
        "Peso Total (kg)",
        "Pontos Totais",
    ])

    for ponto_id, dados in estatistica_por_ponto.items():
        ponto = PontoColeta.query.get(ponto_id)
        nome_ponto = ponto.nome if ponto else f"Ponto #{ponto_id}"

        writer.writerow([
            nome_ponto,
            dados["qtd_descartes"],
            f"{dados['peso_total']:.2f}",
            dados["pontos_totais"],
        ])

    csv_data = output.getvalue()
    output.close()

    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = \
        "attachment; filename=relatorio_gestor_resumo_pontos_ecosmart.csv"

    return response


# ============= START =============
if __name__ == "__main__":
    app.run(debug=True)
