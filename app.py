import streamlit as st
import datetime
import pandas as pd
import os
import json
from fpdf import FPDF
import shutil
import base64
import logging
import qrcode
from io import BytesIO
from streamlit_option_menu import option_menu # <-- 1. IMPORT THE NEW MENU LIBRARY

# --- Configuration & Global Constants ---
st.set_page_config(
    page_title="Gestion Allo-Greffe",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_UPLOAD_FOLDER = "patient_uploads_allogreffe"
GENERATED_PDF_FOLDER = "generated_reports_allogreffe"
ALLOGREFFE_LOGO_FOOTER = "allogreffe_logo_footer.png" # Make sure you have this image file

ADMIN_DOCS_LIST = ["Extrait d'acte de naissance (Père)", "Extrait d'acte de naissance (Mère)", "Copie intégrale (Receveur)", "Copie intégrale (Donneur)", "Certificat de nationalité (Père)", "Certificat de nationalité (Mère)", "CIN (Père)", "CIN (Mère)", "CIN (Receveur)", "CIN (Donneur)", "Consentement éclairé (Receveur)", "Consentement éclairé (Donneur)"]
MEDICAL_EXAMS_LIST = ["Rx Thorax", "Échographie Cardiaque", "FISH", "Bilan Hépatique", "Bilan Rénal", "Sérologies Virales (VIH, VHB, VHC)", "Consultation Anesthésie", "Typage HLA"]
MINISTERE_DOCS_LIST = ["Rapport Médical", "Certificat médical", "Acte de mariage (si applicable)", "CIN légalisé du père", "CIN légalisé de la Mère", "Demande manuscrite au ministère"]

os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_PDF_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper & Initialization Functions ---
def init_session_state_key(key, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value

def reset_session_state():
    """Resets the form to a blank state for a new patient."""
    # Keep the active page, but clear everything else
    active_page = st.session_state.get('active_page', 'Nouveau Dossier')
    st.session_state.clear()
    st.session_state.active_page = active_page
    initialize_all_form_keys()
    st.session_state.edit_mode = False # Ensure we are not in edit mode
    logging.info("Form state has been reset for a new dossier.")
    # No rerun here, let the menu handler do it

def initialize_all_form_keys():
    """Initializes all form-related keys in session_state to their default values."""
    init_session_state_key('current_step', 0)
    init_session_state_key('edit_mode', False)
    # Patient Info
    init_session_state_key('receveur_ipp', ""); init_session_state_key('receveur_nom', ""); init_session_state_key('receveur_prenom', ""); init_session_state_key('receveur_date_naissance', datetime.date(2000, 1, 1)); init_session_state_key('receveur_adresse', ""); init_session_state_key('receveur_sexe', "Homme"); init_session_state_key('receveur_groupage', "O+"); init_session_state_key('receveur_contact_principal', ""); init_session_state_key('receveur_nom_pere', ""); init_session_state_key('receveur_age_pere', 0); init_session_state_key('receveur_nom_mere', ""); init_session_state_key('receveur_age_mere', 0); init_session_state_key('receveur_organisme', "PAYANT");
    # Donneur Info
    init_session_state_key('donneur_nom', ""); init_session_state_key('donneur_prenom', ""); init_session_state_key('donneur_date_naissance', datetime.date(2000, 1, 1)); init_session_state_key('donneur_adresse', ""); init_session_state_key('donneur_sexe', "Homme"); init_session_state_key('donneur_groupage', "O+"); init_session_state_key('donneur_contact_principal', ""); init_session_state_key('donneur_nom_pere', ""); init_session_state_key('donneur_age_pere', 0); init_session_state_key('donneur_nom_mere', ""); init_session_state_key('donneur_age_mere', 0); init_session_state_key('donneur_organisme', "PAYANT");
    # Documents & Status
    for doc in ADMIN_DOCS_LIST: init_session_state_key(f"admin_doc_{doc.lower().replace(' ', '_').replace('(', '').replace(')', '')}_upload", None)
    init_session_state_key('accord_tribunal', "En cours")
    for exam in MEDICAL_EXAMS_LIST: init_session_state_key(f"medical_exam_{exam.lower().replace(' ', '_').replace('é', 'e').replace('è', 'e')}", False)
    for doc in MINISTERE_DOCS_LIST: init_session_state_key(f"ministere_doc_{doc.lower().replace(' ', '_').replace('è', 'e')}_upload", None)
    init_session_state_key('accord_ministere', "En cours")
    init_session_state_key('organisme_accord_nom_specifique', ""); init_session_state_key('organisme_accord_statut', "En cours"); init_session_state_key('organisme_accord_date_validation', datetime.date.today()); init_session_state_key('organisme_accord_document_upload', None)
    # Search specific state
    init_session_state_key('search_query', '')
    init_session_state_key('search_by', 'IPP')
    init_session_state_key('search_results', [])

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO(); img.save(buffer, format='PNG'); buffer.seek(0)
    return buffer

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode()
    except Exception: return None

# --- PDF Generation (With Fixes) ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            # Important: Ensure you have this font file or change it to a default one.
            self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            self.font_family = 'DejaVu'
        except RuntimeError:
            logging.warning("DejaVuSans.ttf not found. PDF may not render special characters correctly. Please download it and place it in the same folder as the script.")
            self.font_family = 'Arial'

    def header(self): self.set_font(self.font_family, 'B', 14); self.cell(0, 10, 'Dossier Patient Allo-Greffe', 0, 1, 'C'); self.ln(5)
    def footer(self): self.set_y(-15); self.set_font(self.font_family, 'I', 8); self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    def chapter_title(self, title): self.set_font(self.font_family, 'B', 12); self.set_fill_color(220, 230, 240); self.cell(0, 8, title, 0, 1, 'L', fill=True); self.ln(3)

    def chapter_body(self, data_dict):
        label_width = 50
        value_width = self.w - self.l_margin - self.r_margin - label_width - 2
        for key, value in data_dict.items():
            self.set_font(self.font_family, 'B', 10); self.cell(label_width, 6, f"{key.replace('_', ' ').title()}: ", 0, 0)
            self.set_font(self.font_family, '', 10); self.multi_cell(value_width, 6, str(value), 0, 'L')
        self.ln(2)

    def check_list(self, title, items_dict):
        self.chapter_title(title)
        for item, status in items_dict.items():
            self.set_font(self.font_family, 'B' if status else '', 10)
            self.cell(0, 7, f"- {item}: {'Oui' if status else 'Non'}", 0, 1)
        self.ln(4)

def save_uploaded_file(uploaded_file, subfolder):
    if uploaded_file is None: return None
    ipp = st.session_state.get('receveur_ipp')
    if not ipp: st.error("IPP du receveur n'est pas défini. Impossible de sauvegarder le fichier."); return None
    patient_folder = os.path.join(BASE_UPLOAD_FOLDER, ipp, subfolder); os.makedirs(patient_folder, exist_ok=True)
    file_path = os.path.join(patient_folder, uploaded_file.name)
    with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())
    logging.info(f"Fichier sauvegardé : {file_path}"); return file_path

def generate_pdf_report(state, output_filename):
    pdf = PDF('P', 'mm', 'A4'); pdf.set_auto_page_break(auto=True, margin=15); pdf.add_page()
    receveur_info = {"IPP": state.get('receveur_ipp'),"Nom Complet": f"{state.get('receveur_nom', '')} {state.get('receveur_prenom', '')}","Date de Naissance": str(state.get('receveur_date_naissance')),"Sexe": state.get('receveur_sexe'),"Adresse": state.get('receveur_adresse'),"Organisme Payeur": state.get('receveur_organisme')}
    pdf.chapter_title("Informations sur le Receveur"); pdf.chapter_body(receveur_info)
    donneur_info = {"Nom Complet": f"{state.get('donneur_nom', '')} {state.get('donneur_prenom', '')}","Date de Naissance": str(state.get('donneur_date_naissance')),"Sexe": state.get('donneur_sexe')}
    pdf.chapter_title("Informations sur le Donneur"); pdf.chapter_body(donneur_info)
    status_info = {"Accord Tribunal": state.get('accord_tribunal'),"Accord Ministère": state.get('accord_ministere'),"Accord Organisme": state.get('organisme_accord_statut')}
    pdf.chapter_title("Statuts des Accords"); pdf.chapter_body(status_info)
    medical_exams_status = {exam: state.get(f"medical_exam_{exam.lower().replace(' ', '_').replace('é', 'e').replace('è', 'e')}") for exam in MEDICAL_EXAMS_LIST}
    pdf.check_list("Check-list des Examens Médicaux", medical_exams_status)
    pdf.output(output_filename, 'F'); logging.info(f"Rapport PDF généré : {output_filename}"); return output_filename

# --- UI Rendering Functions ---
def _inject_custom_styles():
    # --- 2. IMPROVED CSS: I added the .block-container rule to reduce top space ---
    st.markdown("""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            /* --- CSS Rule to reduce top space --- */
            .block-container {
                padding-top: 2rem !important;
            }
            :root{
                --primary-color:#2563eb;
                --primary-dark:#1d4ed8;
                --secondary-color:#10b981;
                --accent-color:#f59e0b;
                --danger-color:#ef4444;
                --surface-light:#ffffff;
                --text-light:#374151;
                --border-light:#e5e7eb;
            }
            body{font-family:'Inter',sans-serif;}
            .stApp > header, #MainMenu, footer {visibility:hidden;}
            .step-navigation {
                display:flex;
                justify-content:center;
                align-items:center;
                flex-wrap:wrap;
                gap:10px;
                margin-bottom: 2rem;
                padding:1rem;
                background:#f8fafc;
                border-radius:16px;
                border:1px solid var(--border-light);
            }
            .step-item{display:flex;align-items:center;margin:0 .5rem;padding:.5rem 1rem;border-radius:12px;font-weight:600;transition:all .3s ease;}
            .step-item.active{background:linear-gradient(135deg,var(--primary-color) 0%,var(--primary-dark) 100%);color:white;transform:scale(1.05);box-shadow:0 8px 16px rgba(37,99,235,.3);}
            .step-item.completed{background:linear-gradient(135deg,var(--secondary-color) 0%,#059669 100%);color:white;}
            .step-item.inactive{background:#f1f5f9;color:#64748b;}
            .page-header{padding:2rem;background:linear-gradient(135deg,var(--primary-color) 0%,var(--primary-dark) 100%);color:white;border-radius:20px;margin-bottom:2rem;box-shadow:0 10px 25px rgba(37,99,235,.3);}
            .page-header h2{margin:0;font-size:2.2rem;font-weight:700;}
            .page-header p.subtitle{margin:.5rem 0 0 0;opacity:.9;font-size:1.1rem;}
        </style>
    """, unsafe_allow_html=True)


def render_step_navigation():
    steps = [{"name": "Étape 1", "title": "Receveur", "icon": "fas fa-user-injured"}, {"name": "Étape 2", "title": "Donneur", "icon": "fas fa-user-friends"}, {"name": "Étape 3", "title": "Tribunaux", "icon": "fas fa-gavel"}, {"name": "Étape 4", "title": "Médical", "icon": "fas fa-file-medical-alt"}, {"name": "Étape 5", "title": "Ministère", "icon": "fas fa-landmark"}, {"name": "Étape 6", "title": "Organisme", "icon": "fas fa-hands-helping"}, {"name": "Étape 7", "title": "Confirmation", "icon": "fas fa-check-circle"}]
    current_step = st.session_state.current_step
    step_html = '<div class="step-navigation">'
    for i, step in enumerate(steps):
        status_class = "active" if i == current_step else ("completed" if i < current_step else "inactive")
        step_html += f'<div class="step-item {status_class}"><i class="{step["icon"]}" style="margin-right:8px;"></i><div><div style="font-size:0.8rem;opacity:0.8;">{step["name"]}</div><div style="font-size:0.9rem;">{step["title"]}</div></div></div>'
    st.markdown(step_html + '</div>', unsafe_allow_html=True)

def render_navigation_buttons():
    st.markdown("---")
    cols = st.columns([1, 1, 1, 1, 1])
    with cols[0]:
        if st.session_state.current_step > 0:
            if st.button("← Précédent", use_container_width=True): st.session_state.current_step -= 1; st.rerun()
    with cols[4]:
        if st.session_state.current_step < 6:
            if st.button("Suivant →", type="primary", use_container_width=True): st.session_state.current_step += 1; st.rerun()

# --- Page Renderers (No changes needed in these functions) ---
def render_receveur_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-user-injured"></i> Informations sur le Receveur</h2><p class="subtitle">Détails personnels et administratifs du patient receveur.</p></div>', unsafe_allow_html=True)
    if st.session_state.edit_mode:
        st.info(f"**Mode Modification** | Vous modifiez le dossier du patient **{st.session_state.get('receveur_nom')} {st.session_state.get('receveur_prenom')}** (IPP: **{st.session_state.get('receveur_ipp')}**)")
        st.text_input("IPP", st.session_state.receveur_ipp, disabled=True)
    else:
        st.warning("⚠️ L'IPP est obligatoire et sera utilisé pour créer le dossier du patient.")
        st.session_state.receveur_ipp = st.text_input("IPP", st.session_state.receveur_ipp)

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.receveur_nom = st.text_input("Nom", st.session_state.receveur_nom)
            st.session_state.receveur_prenom = st.text_input("Prénom", st.session_state.receveur_prenom)
            st.session_state.receveur_date_naissance = st.date_input("Date de Naissance", st.session_state.receveur_date_naissance)
        with col2:
            st.session_state.receveur_sexe = st.radio("Sexe", ["Homme", "Femme"], index=["Homme", "Femme"].index(st.session_state.receveur_sexe), horizontal=True)
            st.session_state.receveur_groupage = st.selectbox("Groupage Sanguin", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], index=["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].index(st.session_state.receveur_groupage))
            st.session_state.receveur_contact_principal = st.text_input("Contact Principal", st.session_state.receveur_contact_principal)
            st.session_state.receveur_organisme = st.selectbox("Organisme Payeur", ["PAYANT", "CNAM", "CNOPS", "AXA", "FAR- Sociales", "Autre"], index=["PAYANT", "CNAM", "CNOPS", "AXA", "FAR- Sociales", "Autre"].index(st.session_state.receveur_organisme))
        st.session_state.receveur_adresse = st.text_area("Adresse", st.session_state.receveur_adresse, height=100)
    with st.container(border=True):
        st.subheader("Informations Parents du Receveur")
        col_p1, col_p2 = st.columns(2);
        with col_p1: st.session_state.receveur_nom_pere = st.text_input("Nom du Père", st.session_state.receveur_nom_pere); st.session_state.receveur_nom_mere = st.text_input("Nom de la Mère", st.session_state.receveur_nom_mere)
        with col_p2: st.session_state.receveur_age_pere = st.number_input("Âge du Père", 0, 120, st.session_state.receveur_age_pere); st.session_state.receveur_age_mere = st.number_input("Âge de la Mère", 0, 120, st.session_state.receveur_age_mere)

def render_donneur_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-user-friends"></i> Informations sur le Donneur</h2></div>', unsafe_allow_html=True)
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1: st.session_state.donneur_nom = st.text_input("Nom du Donneur", st.session_state.donneur_nom); st.session_state.donneur_prenom = st.text_input("Prénom du Donneur", st.session_state.donneur_prenom)
        with col2: st.session_state.donneur_date_naissance = st.date_input("Date de Naissance du Donneur", st.session_state.donneur_date_naissance); st.session_state.donneur_sexe = st.radio("Sexe du Donneur", ["Homme", "Femme"], index=["Homme", "Femme"].index(st.session_state.donneur_sexe), horizontal=True)

def render_tribunaux_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-gavel"></i> Dossier Tribunal</h2></div>', unsafe_allow_html=True)
    with st.container(border=True): st.session_state.accord_tribunal = st.selectbox("Statut de l'accord du Tribunal", ["En cours", "Accordé", "Refusé"], index=["En cours", "Accordé", "Refusé"].index(st.session_state.accord_tribunal))
    with st.container(border=True):
        st.subheader("Documents Administratifs Requis")
        if not st.session_state.receveur_ipp: st.error("Veuillez renseigner l'IPP du receveur à l'étape 1 pour joindre des fichiers."); return
        cols = st.columns(2)
        for i, doc in enumerate(ADMIN_DOCS_LIST):
            doc_key = f"admin_doc_{doc.lower().replace(' ', '_').replace('(', '').replace(')', '')}_upload"
            with cols[i % 2]:
                if st.session_state.get(doc_key) and isinstance(st.session_state.get(doc_key), str):
                    st.success(f"Fichier existant: '{os.path.basename(st.session_state[doc_key])}'")
                uploaded_file = st.file_uploader(f"Joindre/Remplacer: {doc}", type=['pdf', 'jpg', 'png'], key=f"uploader_{doc_key}")
                if uploaded_file:
                    st.session_state[doc_key] = save_uploaded_file(uploaded_file, "tribunal")
                    st.rerun()

def render_medical_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-file-medical-alt"></i> Dossier Médical</h2></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Statut des examens médicaux")
        cols = st.columns(3)
        for i, exam in enumerate(MEDICAL_EXAMS_LIST):
            exam_key = f"medical_exam_{exam.lower().replace(' ', '_').replace('é', 'e').replace('è', 'e')}"
            with cols[i % 3]: st.session_state[exam_key] = st.checkbox(exam, value=st.session_state.get(exam_key, False))

def render_ministere_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-landmark"></i> Dossier Ministère</h2></div>', unsafe_allow_html=True)
    with st.container(border=True): st.session_state.accord_ministere = st.selectbox("Statut de l'accord du Ministère", ["En cours", "Accordé", "Refusé"], index=["En cours", "Accordé", "Refusé"].index(st.session_state.accord_ministere))
    with st.container(border=True):
        st.subheader("Documents Requis pour le Ministère")
        if not st.session_state.receveur_ipp: st.error("Veuillez renseigner l'IPP du receveur à l'étape 1 pour joindre des fichiers."); return
        cols = st.columns(2)
        for i, doc in enumerate(MINISTERE_DOCS_LIST):
            doc_key = f"ministere_doc_{doc.lower().replace(' ', '_').replace('è', 'e')}_upload"
            with cols[i % 2]:
                if st.session_state.get(doc_key) and isinstance(st.session_state.get(doc_key), str):
                    st.success(f"Fichier existant: '{os.path.basename(st.session_state[doc_key])}'")
                uploaded_file = st.file_uploader(f"Joindre/Remplacer: {doc}", type=['pdf', 'jpg', 'png'], key=f"uploader_{doc_key}")
                if uploaded_file:
                    st.session_state[doc_key] = save_uploaded_file(uploaded_file, "ministere")
                    st.rerun()

def render_organisme_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-hands-helping"></i> Dossier Organisme Payeur</h2></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.session_state.organisme_accord_statut = st.selectbox("Statut de l'accord", ["En cours", "Accordé", "Refusé"], index=["En cours", "Accordé", "Refusé"].index(st.session_state.organisme_accord_statut))
        st.session_state.organisme_accord_date_validation = st.date_input("Date de validation de l'accord", st.session_state.organisme_accord_date_validation)
        if not st.session_state.receveur_ipp: st.error("Veuillez renseigner l'IPP du receveur à l'étape 1 pour joindre un fichier.")
        else:
            if st.session_state.get('organisme_accord_document_upload') and isinstance(st.session_state.get('organisme_accord_document_upload'), str):
                st.success(f"Fichier existant: '{os.path.basename(st.session_state['organisme_accord_document_upload'])}'")
            uploaded_file = st.file_uploader("Joindre/Remplacer le document de l'accord", type=['pdf', 'jpg', 'png'], key="uploader_organisme_accord")
            if uploaded_file:
                st.session_state.organisme_accord_document_upload = save_uploaded_file(uploaded_file, "organisme")
                st.rerun()

def render_confirmation_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-check-circle"></i> Confirmation et Soumission</h2></div>', unsafe_allow_html=True)
    if st.session_state.edit_mode:
        st.info(f"Vous êtes sur le point de **mettre à jour** le dossier du patient **{st.session_state.get('receveur_nom')} {st.session_state.get('receveur_prenom')}**.")
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("📝 Récapitulatif Receveur", expanded=True): st.write(f"**IPP:** {st.session_state.receveur_ipp}"); st.write(f"**Nom Complet:** {st.session_state.receveur_nom} {st.session_state.receveur_prenom}"); st.write(f"**Date de Naissance:** {st.session_state.receveur_date_naissance.strftime('%d/%m/%Y')}")
        with st.expander("⚖️ Statuts des Accords", expanded=True): st.write(f"**Tribunal:** {st.session_state.accord_tribunal}"); st.write(f"**Ministère:** {st.session_state.accord_ministere}"); st.write(f"**Organisme:** {st.session_state.organisme_accord_statut}")
    with col2:
        with st.expander("📝 Récapitulatif Donneur", expanded=True): st.write(f"**Nom Complet:** {st.session_state.donneur_nom} {st.session_state.donneur_prenom}"); st.write(f"**Date de Naissance:** {st.session_state.donneur_date_naissance.strftime('%d/%m/%Y')}")
    st.markdown("---")
    button_label = "Mettre à Jour le Dossier" if st.session_state.edit_mode else "Générer et Enregistrer le Dossier"
    if st.button(button_label, type="primary", use_container_width=True):
        if not st.session_state.receveur_ipp: st.error("L'IPP du receveur est obligatoire pour sauvegarder le dossier."); return
        patient_folder = os.path.join(BASE_UPLOAD_FOLDER, st.session_state.receveur_ipp); os.makedirs(patient_folder, exist_ok=True)
        data_to_save = {}
        for k, v in st.session_state.items():
            if hasattr(v, 'read') or k.startswith('uploader_') or k.startswith('FormSubmitter'): continue
            if isinstance(v, (datetime.date, datetime.datetime)): data_to_save[k] = v.isoformat()
            else: data_to_save[k] = v
        with open(os.path.join(patient_folder, "data.json"), 'w', encoding='utf-8') as f: json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        pdf_filename = os.path.join(GENERATED_PDF_FOLDER, f"Rapport_{st.session_state.receveur_ipp}.pdf"); generate_pdf_report(st.session_state, pdf_filename)
        st.success(f"Dossier pour le patient IPP `{st.session_state.receveur_ipp}` a été sauvegardé avec succès!"); st.balloons()
        with open(pdf_filename, "rb") as pdf_file: st.download_button(label="Télécharger le Rapport PDF", data=pdf_file, file_name=os.path.basename(pdf_filename), mime="application/octet-stream", use_container_width=True)

def render_dashboard_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-tachometer-alt"></i> Tableau de Bord des Dossiers</h2></div>', unsafe_allow_html=True)
    dossiers = []
    if os.path.exists(BASE_UPLOAD_FOLDER):
        for ipp_folder in sorted(os.listdir(BASE_UPLOAD_FOLDER)):
            json_path = os.path.join(BASE_UPLOAD_FOLDER, ipp_folder, "data.json")
            if os.path.isfile(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
                    dossiers.append({"IPP": data.get("receveur_ipp", "N/A"), "Nom Receveur": f"{data.get('receveur_nom', '')} {data.get('receveur_prenom', '')}", "Accord Tribunal": data.get("accord_tribunal", "N/A"), "Accord Ministère": data.get("accord_ministere", "N/A"), "Nom Donneur": f"{data.get('donneur_nom', '')} {data.get('donneur_prenom', '')}"})
                except json.JSONDecodeError: logging.error(f"Could not decode JSON for patient {ipp_folder}")
    if not dossiers: st.info("Aucun dossier patient n'a été trouvé."); return
    st.dataframe(pd.DataFrame(dossiers), use_container_width=True)


def search_for_patient(query, search_by):
    matches = []
    if not query: return matches
    query = query.lower()
    for ipp_folder in os.listdir(BASE_UPLOAD_FOLDER):
        json_path = os.path.join(BASE_UPLOAD_FOLDER, ipp_folder, "data.json")
        if os.path.isfile(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    patient_ipp = data.get('receveur_ipp', '').lower()
                    patient_name = f"{data.get('receveur_nom', '')} {data.get('receveur_prenom', '')}".lower()
                    if (search_by == 'IPP' and query in patient_ipp) or (search_by == 'Nom' and query in patient_name):
                        matches.append({'ipp': data.get('receveur_ipp', 'N/A'), 'name': f"{data.get('receveur_nom', '')} {data.get('receveur_prenom', '')}"})
                except (json.JSONDecodeError, KeyError): continue
    return matches

def load_patient_data(ipp):
    json_path = os.path.join(BASE_UPLOAD_FOLDER, ipp, "data.json")
    if not os.path.isfile(json_path): st.error(f"Fichier de données introuvable pour l'IPP {ipp}."); return
    with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
    active_page = st.session_state.active_page; st.session_state.clear();
    initialize_all_form_keys()
    for key, value in data.items():
        if isinstance(value, str):
            try: st.session_state[key] = datetime.datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError: st.session_state[key] = value
        else: st.session_state[key] = value
    st.session_state.active_page = "Nouveau Dossier"; st.session_state.edit_mode = True; st.session_state.current_step = 0; st.rerun()

def render_search_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-search"></i> Rechercher / Modifier un Dossier</h2></div>', unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1: st.session_state.search_query = st.text_input("Rechercher un patient", st.session_state.search_query, placeholder="Entrez un IPP ou un nom...")
    with col2: st.session_state.search_by = st.selectbox("Rechercher par", ["IPP", "Nom"], index=["IPP", "Nom"].index(st.session_state.search_by))
    if st.button("Lancer la recherche", type="primary"): st.session_state.search_results = search_for_patient(st.session_state.search_query, st.session_state.search_by)
    st.markdown("---")
    if st.session_state.search_results:
        st.subheader(f"Résultats de la recherche ({len(st.session_state.search_results)} trouvés)")
        for patient in st.session_state.search_results:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**Nom:** {patient['name']}<br>**IPP:** {patient['ipp']}", unsafe_allow_html=True)
                if c2.button("Modifier ce dossier", key=f"load_{patient['ipp']}", use_container_width=True): load_patient_data(patient['ipp'])
    elif st.session_state.search_query: st.info("Aucun dossier correspondant à votre recherche n'a été trouvé.")

# --- Main Application ---
def main():
    _inject_custom_styles()
    init_session_state_key('active_page', 'Nouveau Dossier')
    if 'current_step' not in st.session_state:
        initialize_all_form_keys()

    # --- 3. REPLACED SIDEBAR: This is the new, nice-looking menu ---
    with st.sidebar:
        st.title("👨‍⚕️ Gestion Allo-Greffe")
        st.markdown("---")

        # Define a list of page names corresponding to the menu titles
        page_options = ["Nouveau Dossier", "Rechercher / Modifier", "Tableau de Bord"]
        
        # Get the current page index for the default_index parameter
        try:
            default_index = page_options.index(st.session_state.active_page)
        except ValueError:
            default_index = 0

        selected_page = option_menu(
            menu_title=None,  # Hides the default menu title
            options=page_options,
            icons=["plus-square-fill", "search", "bar-chart-fill"],
            menu_icon="cast",
            default_index=default_index,
        )

        # Update the active page and handle resets
        if selected_page != st.session_state.active_page:
            st.session_state.active_page = selected_page
            if selected_page == "Nouveau Dossier":
                reset_session_state()
            st.rerun()

        st.markdown("---")
        logo = get_base64_image(ALLOGREFFE_LOGO_FOOTER)
        if logo:
            st.markdown(f'<div style="text-align: center; padding: 1rem;"><img src="data:image/png;base64,{logo}" width="100"></div>', unsafe_allow_html=True)


    # --- Page Routing ---
    if st.session_state.active_page == "Nouveau Dossier":
        render_step_navigation()
        page_renderers = [render_receveur_page, render_donneur_page, render_tribunaux_page, render_medical_page, render_ministere_page, render_organisme_page, render_confirmation_page]
        page_renderers[st.session_state.current_step]()
        if st.session_state.current_step < 6:
            render_navigation_buttons()
    elif st.session_state.active_page == "Tableau de Bord":
        render_dashboard_page()
    elif st.session_state.active_page == "Rechercher / Modifier":
        render_search_page()


if __name__ == "__main__":
    main()
