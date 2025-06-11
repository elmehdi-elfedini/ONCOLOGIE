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

# --- Configuration & Global Constants ---
st.set_page_config(
    page_title="Gestion Allo-Greffe",
    layout="wide",
    initial_sidebar_state="expanded" # Expanded to show navigation
)

BASE_UPLOAD_FOLDER = "patient_uploads_allogreffe"
GENERATED_PDF_FOLDER = "generated_reports_allogreffe"
ALLOGREFFE_LOGO_FOOTER = "allogreffe_logo_footer.png" # Make sure this logo exists or remove the reference

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
    active_page = st.session_state.get('active_page', 'Dossier Patient')
    st.session_state.clear()
    st.session_state.active_page = active_page
    initialize_all_form_keys()
    st.session_state.edit_mode = False
    logging.info("Form state has been reset for a new dossier.")
    st.rerun()

def initialize_all_form_keys():
    """Initializes all form-related keys in session_state to their default values."""
    init_session_state_key('active_page', 'Dossier Patient')
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
            # Note: You must have the DejaVuSans.ttf font file in the same directory as your script
            # or provide the full path to it.
            self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            self.font_family = 'DejaVu'
        except RuntimeError:
            logging.warning("DejaVuSans.ttf not found. PDF may not render special characters correctly. Using Arial.")
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
            checkbox = '[X]' if status else '[ ]'
            self.set_font(self.font_family, '', 10)
            self.cell(0, 7, f"{checkbox} {item}", 0, 1)
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

# --- Data Persistence ---
def serialize_state(state):
    """Converts session_state to a JSON-serializable dictionary."""
    serializable_state = {}
    for k, v in state.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            serializable_state[k] = v.isoformat()
        elif isinstance(v, (str, int, float, bool, list)) or v is None:
            serializable_state[k] = v
        # Note: We ignore non-serializable types like UploadedFile objects, functions, etc.
        # File paths are strings, so they are saved correctly.
    return serializable_state

def save_patient_data(state):
    """Saves the current session state to a JSON file in the patient's folder."""
    ipp = state.get('receveur_ipp')
    if not ipp:
        st.error("L'IPP du receveur est obligatoire pour la sauvegarde.")
        return False
    patient_folder = os.path.join(BASE_UPLOAD_FOLDER, ipp)
    os.makedirs(patient_folder, exist_ok=True)
    json_path = os.path.join(patient_folder, "patient_data.json")
    data_to_save = serialize_state(state)
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        logging.info(f"Données du patient {ipp} sauvegardées dans {json_path}")
        return True
    except Exception as e:
        logging.error(f"Erreur lors de la sauvegarde des données pour {ipp}: {e}")
        st.error(f"Une erreur est survenue lors de la sauvegarde: {e}")
        return False

def load_patient_data(ipp):
    """Loads a patient's data from their JSON file into the session state."""
    json_path = os.path.join(BASE_UPLOAD_FOLDER, ipp, "patient_data.json")
    if not os.path.exists(json_path):
        st.error(f"Aucun dossier trouvé pour l'IPP: {ipp}")
        return False
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reset state before loading new data, preserving active page
        active_page = st.session_state.get('active_page')
        st.session_state.clear()
        initialize_all_form_keys() # Re-initialize to avoid key errors
        st.session_state.active_page = active_page

        for key, value in data.items():
            # Attempt to convert ISO date strings back to date objects
            if isinstance(value, str):
                try:
                    st.session_state[key] = datetime.datetime.fromisoformat(value).date()
                    continue
                except (ValueError, TypeError): pass # Not a date string
            st.session_state[key] = value
        
        st.session_state.edit_mode = True
        st.session_state.active_page = 'Dossier Patient'
        st.session_state.current_step = 0
        logging.info(f"Dossier du patient {ipp} chargé avec succès.")
        return True
    except Exception as e:
        logging.error(f"Erreur lors du chargement des données pour {ipp}: {e}")
        st.error(f"Erreur de chargement du dossier: {e}")
        return False

def delete_patient_folder(ipp):
    """Deletes the entire folder for a given patient IPP."""
    patient_folder = os.path.join(BASE_UPLOAD_FOLDER, ipp)
    if os.path.isdir(patient_folder):
        try:
            shutil.rmtree(patient_folder)
            logging.info(f"Dossier pour l'IPP {ipp} supprimé.")
            st.success(f"Le dossier du patient {ipp} a été supprimé.")
            return True
        except Exception as e:
            logging.error(f"Erreur lors de la suppression du dossier {ipp}: {e}")
            st.error(f"Erreur lors de la suppression: {e}")
            return False
    return False

# --- UI Rendering Functions ---
def _inject_custom_styles():
    st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
    :root {
        --primary-color: #2563eb; --primary-dark: #1d4ed8; --secondary-color: #10b981;
        --danger-color: #ef4444; --surface-light: #ffffff; --text-light: #374151;
        --border-light: #e5e7eb; --sidebar-bg: #f8fafc; --sidebar-hover: #e2e8f0;
    }
    .stApp > header, #MainMenu, footer { visibility: hidden; }
    .main .block-container { padding-top: 1rem !important; padding-bottom: 2rem; }
    .css-1d391kg { background: linear-gradient(135deg, var(--sidebar-bg) 0%, #ffffff 100%); border-right: 2px solid var(--border-light); box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1); }
    .css-1d391kg h1 { color: var(--primary-color); font-weight: 700; text-align: center; padding: 1rem 0; margin-bottom: 0; border-bottom: 2px solid var(--primary-color); background: linear-gradient(135deg, var(--primary-color), var(--primary-dark)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
    .css-1d391kg .stButton > button { width: 100%; background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%); color: white; border: none; border-radius: 12px; padding: 0.75rem 1rem; font-weight: 600; font-size: 0.95rem; margin: 0.25rem 0; transition: all 0.3s ease; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2); }
    .css-1d391kg .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(37, 99, 235, 0.3); background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary-color) 100%); }
    .css-1d391kg hr { border: none; height: 2px; background: linear-gradient(90deg, transparent, var(--primary-color), transparent); margin: 1rem 0; }
    .step-navigation { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 10px; margin: 1rem 0 2rem 0; padding: 1rem; background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%); border-radius: 16px; border: 1px solid var(--border-light); box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); }
    .step-item { display: flex; align-items: center; margin: 0 0.5rem; padding: 0.5rem 1rem; border-radius: 12px; font-weight: 600; transition: all 0.3s ease; min-width: 120px; justify-content: center; }
    .step-item.active { background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%); color: white; transform: scale(1.05); box-shadow: 0 8px 16px rgba(37, 99, 235, 0.3); }
    .step-item.completed { background: linear-gradient(135deg, var(--secondary-color) 0%, #059669 100%); color: white; box-shadow: 0 4px 8px rgba(16, 185, 129, 0.2); }
    .step-item.inactive { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }
    .page-header { padding: 2rem; background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%); color: white; border-radius: 20px; margin-bottom: 2rem; box-shadow: 0 10px 25px rgba(37, 99, 235, 0.3); text-align: center; }
    .page-header h2 { margin: 0; font-size: 2.2rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); }
    body { font-family: 'Inter', sans-serif; }
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

# --- Page Renderers ---
def render_receveur_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-user-injured"></i> Informations sur le Receveur</h2></div>', unsafe_allow_html=True)
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
                if st.session_state.get(doc_key) and os.path.exists(st.session_state[doc_key]):
                    st.success(f"✔ {doc}: Fichier joint ({os.path.basename(st.session_state[doc_key])})")
                
                # Using a unique key for the uploader widget itself is crucial
                uploaded_file = st.file_uploader(f"Joindre : {doc}", key=f"uploader_{doc_key}", type=['pdf', 'png', 'jpg', 'jpeg'])
                
                if uploaded_file is not None:
                    file_path = save_uploaded_file(uploaded_file, "documents_tribunaux")
                    if file_path:
                        st.session_state[doc_key] = file_path
                        st.rerun() # Rerun to update the success message and clear the uploader

def render_medical_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-file-medical-alt"></i> Examens Médicaux</h2></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Check-list des Examens Médicaux du Donneur")
        cols = st.columns(2)
        for i, exam in enumerate(MEDICAL_EXAMS_LIST):
            exam_key = f"medical_exam_{exam.lower().replace(' ', '_').replace('é', 'e').replace('è', 'e')}"
            with cols[i % 2]:
                st.session_state[exam_key] = st.checkbox(exam, value=st.session_state.get(exam_key, False))

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
                if st.session_state.get(doc_key) and os.path.exists(st.session_state[doc_key]):
                    st.success(f"✔ {doc}: Fichier joint ({os.path.basename(st.session_state[doc_key])})")
                uploaded_file = st.file_uploader(f"Joindre : {doc}", key=f"uploader_{doc_key}", type=['pdf', 'png', 'jpg', 'jpeg'])
                if uploaded_file is not None:
                    file_path = save_uploaded_file(uploaded_file, "documents_ministere")
                    if file_path:
                        st.session_state[doc_key] = file_path
                        st.rerun()

def render_organisme_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-hands-helping"></i> Accord Organisme</h2></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Validation par l'Organisme Payeur")
        st.info(f"Organisme sélectionné: **{st.session_state.receveur_organisme}**")
        if st.session_state.receveur_organisme == "Autre":
            st.session_state.organisme_accord_nom_specifique = st.text_input("Nom de l'organisme spécifique", st.session_state.organisme_accord_nom_specifique)
        
        st.session_state.organisme_accord_statut = st.selectbox("Statut de l'accord", ["En cours", "Accordé", "Refusé"], index=["En cours", "Accordé", "Refusé"].index(st.session_state.organisme_accord_statut))
        st.session_state.organisme_accord_date_validation = st.date_input("Date de validation (si applicable)", st.session_state.organisme_accord_date_validation)
        
        doc_key = 'organisme_accord_document_upload'
        if st.session_state.get(doc_key) and os.path.exists(st.session_state[doc_key]):
            st.success(f"✔ Document d'accord joint ({os.path.basename(st.session_state[doc_key])})")
        uploaded_file = st.file_uploader("Joindre le document d'accord", key=f"uploader_{doc_key}", type=['pdf', 'png', 'jpg', 'jpeg'])
        if uploaded_file is not None:
            file_path = save_uploaded_file(uploaded_file, "documents_organisme")
            if file_path:
                st.session_state[doc_key] = file_path
                st.rerun()

def render_confirmation_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-check-circle"></i> Confirmation et Actions</h2></div>', unsafe_allow_html=True)
    st.info("Veuillez vérifier toutes les informations avant de sauvegarder le dossier.")
    
    with st.container(border=True):
        col1, col2 = st.columns([2,1])
        with col1:
            st.subheader("Résumé du Dossier")
            st.write(f"**IPP Receveur:** {st.session_state.receveur_ipp}")
            st.write(f"**Receveur:** {st.session_state.receveur_nom} {st.session_state.receveur_prenom}")
            st.write(f"**Donneur:** {st.session_state.donneur_nom} {st.session_state.donneur_prenom}")
            st.write(f"**Accord Tribunal:** `{st.session_state.accord_tribunal}`")
            st.write(f"**Accord Ministère:** `{st.session_state.accord_ministere}`")
            st.write(f"**Accord Organisme:** `{st.session_state.organisme_accord_statut}`")
        with col2:
            st.subheader("QR Code")
            qr_data = f"IPP: {st.session_state.receveur_ipp}\nNom: {st.session_state.receveur_nom} {st.session_state.receveur_prenom}"
            qr_img = generate_qr_code(qr_data)
            st.image(qr_img, caption="QR Code du Dossier", width=150)

    st.markdown("---")
    st.subheader("Actions")
    
    col_a, col_b, col_c = st.columns([1.5, 1.5, 1])
    with col_a:
        if st.button("💾 Sauvegarder le Dossier", type="primary", use_container_width=True):
            if save_patient_data(st.session_state):
                st.success("Dossier sauvegardé avec succès !")
                st.balloons()
    
    with col_b:
        pdf_path = os.path.join(GENERATED_PDF_FOLDER, f"rapport_{st.session_state.receveur_ipp}.pdf")
        if st.button("📄 Générer le Rapport PDF", use_container_width=True):
            generate_pdf_report(st.session_state, pdf_path)
            st.success(f"Rapport PDF généré : {pdf_path}")
        
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="📥 Télécharger le PDF",
                    data=pdf_file,
                    file_name=os.path.basename(pdf_path),
                    mime="application/octet-stream",
                    use_container_width=True
                )

def render_search_page():
    st.markdown('<div class="page-header"><h2><i class="fas fa-search"></i> Rechercher un Dossier</h2></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([1, 3])
    with c1: st.session_state.search_by = st.selectbox("Rechercher par", ["IPP", "Nom du Receveur"])
    with c2: st.session_state.search_query = st.text_input("Terme de recherche", st.session_state.search_query, placeholder="Entrez l'IPP ou le nom...")
    
    if st.button("Rechercher", type="primary"):
        results = []
        if os.path.exists(BASE_UPLOAD_FOLDER):
            for ipp_folder in os.listdir(BASE_UPLOAD_FOLDER):
                patient_data_path = os.path.join(BASE_UPLOAD_FOLDER, ipp_folder, "patient_data.json")
                if os.path.isdir(os.path.join(BASE_UPLOAD_FOLDER, ipp_folder)) and os.path.exists(patient_data_path):
                    try:
                        with open(patient_data_path, 'r', encoding='utf-8') as f: data = json.load(f)
                        
                        match = False
                        query = st.session_state.search_query.lower()
                        if st.session_state.search_by == 'IPP' and query in data.get('receveur_ipp', '').lower():
                            match = True
                        elif st.session_state.search_by == 'Nom du Receveur':
                            full_name = f"{data.get('receveur_nom', '')} {data.get('receveur_prenom', '')}"
                            if query in full_name.lower():
                                match = True
                        if match: results.append(data)
                    except (json.JSONDecodeError, KeyError) as e:
                        logging.warning(f"Skipping corrupted or invalid data file: {patient_data_path} - {e}")
        st.session_state.search_results = results

    if st.session_state.search_results:
        st.markdown(f"--- \n ### {len(st.session_state.search_results)} résultat(s) trouvé(s)")
        for res in st.session_state.search_results:
            ipp = res.get('receveur_ipp', 'N/A')
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
                with col1:
                    st.markdown(f"**Nom:** {res.get('receveur_nom', '')} {res.get('receveur_prenom', '')}")
                    st.markdown(f"**IPP:** `{ipp}`")
                with col2:
                    st.markdown(f"**Donneur:** {res.get('donneur_nom', '')} {res.get('donneur_prenom', '')}")
                    st.markdown(f"**Date Naissance:** {res.get('receveur_date_naissance', 'N/A')}")
                with col3:
                    if st.button("👁️ Ouvrir / Modifier", key=f"edit_{ipp}", use_container_width=True):
                        if load_patient_data(ipp):
                            st.rerun()
                with col4:
                    if st.button("❌ Supprimer", key=f"delete_{ipp}", type="secondary", use_container_width=True):
                        st.session_state[f'confirm_delete_{ipp}'] = True

                if st.session_state.get(f'confirm_delete_{ipp}'):
                    st.warning(f"Êtes-vous sûr de vouloir supprimer définitivement le dossier de {ipp}? Cette action est irréversible.")
                    c_del1, c_del2 = st.columns(2)
                    if c_del1.button("Oui, supprimer", key=f"confirm_del_btn_{ipp}", type="primary"):
                        delete_patient_folder(ipp)
                        st.session_state.search_results = [r for r in st.session_state.search_results if r.get('receveur_ipp') != ipp]
                        del st.session_state[f'confirm_delete_{ipp}']
                        st.rerun()
                    if c_del2.button("Non, annuler", key=f"cancel_del_btn_{ipp}"):
                        del st.session_state[f'confirm_delete_{ipp}']
                        st.rerun()

# --- Main App ---
def main():
    _inject_custom_styles()
    initialize_all_form_keys()

    with st.sidebar:
        st.markdown("<h1>Gestion Allo-Greffe</h1>", unsafe_allow_html=True)
        st.markdown("---")

        if st.button("➕ Nouveau Dossier", use_container_width=True):
            reset_session_state()
        
        st.markdown("---")
        
        st.subheader("Navigation")
        if st.button("📋 Dossier Patient", use_container_width=True, type="primary" if st.session_state.active_page == 'Dossier Patient' else "secondary"):
            st.session_state.active_page = 'Dossier Patient'
            st.rerun()
        if st.button("🔍 Rechercher Dossier", use_container_width=True, type="primary" if st.session_state.active_page == 'Rechercher Dossier' else "secondary"):
            st.session_state.active_page = 'Rechercher Dossier'
            st.rerun()

    if st.session_state.active_page == 'Dossier Patient':
        render_step_navigation()
        
        page_renderers = [render_receveur_page, render_donneur_page, render_tribunaux_page, render_medical_page, render_ministere_page, render_organisme_page, render_confirmation_page]
        page_renderers[st.session_state.current_step]() # Render the current step's page
        
        render_navigation_buttons()
    
    elif st.session_state.active_page == 'Rechercher Dossier':
        render_search_page()

if __name__ == "__main__":
    main()
