from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_bcrypt import Bcrypt
from flask_login import login_user, logout_user, login_required
from models import db, Usuario

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        bcrypt = Bcrypt(current_app)

        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash("E-mail já cadastrado!", "danger")
            return redirect(url_for("auth.register"))

        senha_hash = bcrypt.generate_password_hash(senha).decode("utf-8")
        usuario = Usuario(nome=nome, email=email, senha_hash=senha_hash)

        db.session.add(usuario)
        db.session.commit()

        flash("Cadastro realizado! Agora faça login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        bcrypt = Bcrypt(current_app)
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and bcrypt.check_password_hash(usuario.senha_hash, senha):
            # Verifica se a conta está ativa antes de permitir o login
            if not usuario.ativo:
                flash("A sua conta está desativada. Entre em contacto com o administrador.", "danger")
                return redirect(url_for("auth.login"))

            login_user(usuario)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("main.index"))

        flash("E-mail ou senha inválidos.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("main.index"))
