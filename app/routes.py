import json
import logging
import boto3
import botocore

import ldclient
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for, session)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.urls import url_parse

from app.factory import CACHE_TIMEOUT, CachingDisabled, cache, db
from app.models import User, Plan


core = Blueprint('core', __name__)

@core.route('/')
def index():
    """
    Controller for Public home page.
    Includes a server side experiment for trial duration. The duration
    can either be 14 days or 30 days. We show a different variation to
    each user randomly. Then we track the registration rate as our
    conversion event.
    """
    current_app.logger.info(current_app.config)
    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))

    user = current_user.get_ld_user()
    session['ld_user'] = user

    longer_trial_duration = ldclient.get().variation(
        'longer-trial-duration',
        user,
        False)

    if longer_trial_duration: # experimentation group
        trial_duration = 30
    else: # control group
        trial_duration = 14

    session['trial_duration'] = trial_duration

    return render_template('home.html', trial_duration=trial_duration)

@core.route('/dashboard')
@login_required
def dashboard():
    theme = request.args.get("theme")
    if theme:
        updateTheme(theme)

    beta_features = ldclient.get().variation('dark-theme', current_user.get_ld_user(), False)

    set_theme = '{0}/index.html'.format(current_user.set_path)

    return render_template(set_theme, title='Home', show_beta=beta_features)

def updateTheme(theme):

    if theme == "dark":
        current_user.set_path = 'beta'
    else:
        current_user.set_path = 'default'

    db.session.commit()

@core.route('/dark')
def darkTheme():
    return render_template(set_theme, title='Dark Theme')

@core.route('/experiments')
def experiments():
    theme = request.args.get("theme")
    if theme:
        updateTheme(theme)

    set_theme = '{0}/exp.html'.format(current_user.set_path)

    random_user = current_user.get_random_ld_user()

    show_nps = ldclient.get().variation('show-nps-survery', random_user, False)

    return render_template(set_theme, title='Experiments', show_nps=show_nps, random_user=random_user)

@core.route('/operational')
def operational():
    theme = request.args.get("theme")
    if theme:
        updateTheme(theme)

    set_theme = '{0}/operation.html'.format(current_user.set_path)

    return render_template(set_theme, title='Operational')

@core.route('/dataexport')
def dataexport():
    embed_url = None
    theme = request.args.get("theme")
    if theme:
        updateTheme(theme)

    user = current_user.get_ld_user()
    session['ld_user'] = user

    # if AWS creds are not set, don't show the dashboard
    try:
        embed_url = fetch_aws_embed_url()
    except botocore.exceptions.NoCredentialsError as e:
        current_app.logger.debug(e)
        
    show_data_export = ldclient.get().variation(
        'data-export',
        user,
        False)

    set_theme = '{0}/dataexport.html'.format(current_user.set_path)

    return render_template(
        set_theme, 
        title='dataexport', 
        embed_url=embed_url,
        show_data_export=show_data_export
    )

@core.route('/release')
def release():
    theme = request.args.get("theme")
    if theme:
        updateTheme(theme)

    set_theme = '{0}/release.html'.format(current_user.set_path)
    return render_template(set_theme, title='Dark Theme')

@core.route('/register', methods=['GET', 'POST'])
def register():
    # track registration attempts
    # ld_user will be in session if user got to the registration
    # page by clicking a link on the home page (where they saw the ab test)
    if session.get('ld_user'):
        current_app.logger.info("Sending track event for {0}".format(session.get('ld_user')))
        ldclient.get().track('started-registration', session['ld_user'])

    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))

    if request.method == 'POST':
        user = User(email=request.form['userEmail'])
        # check if userName exist
        if User.query.filter_by(email = request.form['userEmail']).first() is not None:
            flash('Email is already taken. Please choose another email')
            return redirect(url_for('core.register'))
        # check if passwords match
        if request.form['inputPassword'] != request.form['confirmPassword']:
            flash('Passwords must match')
            return redirect(url_for('core.register'))
        user.set_password(request.form['inputPassword'])
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')

        # track registration completion
        # ld_user will be in session if user got to the registration
        # page by clicking a link on the home page (where they saw the ab test)
        if session.get('ld_user'):
            current_app.logger.info("Sending track event for {0}".format(session.get('ld_user')))
            ldclient.get().track('registered', session['ld_user'])

        login_user(user)
        return redirect(url_for('core.dashboard'))
    return render_template('beta/auth/register.html', title='Support Request')

@core.route('/login', methods=['GET', 'POST'])
def login(theme='default'):
    if current_user.is_authenticated:
        return redirect(url_for('core.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['userEmail']).first()
        if user is None or not user.check_password(request.form['inputPassword']):
            flash('Invalid username or password')
            return redirect(url_for('core.login'))
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('core.dashboard')
        return redirect(next_page)
    return render_template('beta/auth/login.html', title='Sign In')

@core.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('core.index'))

@core.route('/profile')
@login_required
def profile():
    user = User.query.filter_by(id=current_user.id).first()
    return render_template(
        'default/profile.html',
        user=user
    )

@core.route('/people')
@cache.cached(timeout=CACHE_TIMEOUT(), unless=CachingDisabled())
@login_required
def people():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.id).paginate(page, 15, False)
    next_url = url_for('core.people', page=users.next_num) \
        if users.has_next else None
    prev_url = url_for('core.people', page=users.prev_num) \
        if users.has_prev else None
    return render_template(
        'default/people.html',
        users=users.items,
        next_url=next_url,
        prev_url=prev_url
    )

@core.route('/settings')
@login_required
def settings():
    plans = Plan.query.all()
    return render_template(
        'default/settings.html',
        plans=plans
    )

@core.route('/upgrade')
@login_required
def upgrade():
    current_user.plan_id = request.args.get('plan')
    db.session.commit()

    return redirect(request.referrer)

def fetch_aws_embed_url():
    """
    This function is used to generate a new embedded url 
    key each time the data export page is requested
    """
    client = boto3.client(
        'quicksight', 
        region_name = 'us-west-2', 
        aws_access_key_id = current_app.config['AWS_QUICKSIGHT_ACCESS_KEY_ID'],
        aws_secret_access_key = current_app.config['AWS_QUICKSIGHT_SECRET_ACCESS_KEY_ID']
    )

    response = client.get_dashboard_embed_url(
        AwsAccountId='955116512041',
        DashboardId='3d69e3e3-304c-480c-8388-c26bddfa7912',
        IdentityType='IAM',
        SessionLifetimeInMinutes=100,
        UndoRedoDisabled=True,
        ResetDisabled=True
    )
    embedUrl = response.get('EmbedUrl')
    return embedUrl
