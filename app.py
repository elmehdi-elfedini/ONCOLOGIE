# -*- coding: utf-8 -*-
import streamlit as st
import datetime
import pandas as pd
import os
import json
from fpdf import FPDF
import shutil # Keep if used, though not in the provided snippet
import base64
import logging
import qrcode
from io import BytesIO
from streamlit_option_menu import option_menu
from dateutil.relativedelta import relativedelta # Added from first script, might be useful

# --- Configuration & Global Constants from Second Script ---
BASE_UPLOAD_FOLDER = "patient_uploads_allogreffe"
GENERATED_PDF_FOLDER = "generated_reports_allogreffe"
# ALLOGREFFE_LOGO_FOOTER = "allogreffe_logo_footer.png" # We'll use LOGO_PATH from first script's style

ADMIN_DOCS_LIST = ["Extrait d'acte de naissance (Père)", "Extrait d'acte de naissance (Mère)", "Copie intégrale (Receveur)", "Copie intégrale (Donneur)", "Certificat de nationalité (Père)", "Certificat de nationalité (Mère)", "CIN (Père)", "CIN (Mère)", "CIN (Receveur)", "CIN (Donneur)", "Consentement éclairé (Receveur)", "Consentement éclairé (Donneur)"]
MEDICAL_EXAMS_LIST = ["Rx Thorax", "Échographie Cardiaque", "FISH", "Bilan Hépatique", "Bilan Rénal", "Sérologies Virales (VIH, VHB, VHC)", "Consultation Anesthésie", "Typage HLA"]
MINISTERE_DOCS_LIST = ["Rapport Médical", "Certificat médical", "Acte de mariage (si applicable)", "CIN légalisé du père", "CIN légalisé de la Mère", "Demande manuscrite au ministère"]

# --- Configuration Constants from First Script (Adapted) ---
LOGO_PATH = "HM6_Logo.png"        # Main logo, used in footer (ensure this file exists)
LOGO_PATH_2 = "HM6_Logo.png"            # Logo for sidebar (ensure this file exists)
# If you want to use the Allo-Greffe logo for both:
# LOGO_PATH = "allogreffe_logo_footer.png"
# LOGO_PATH_2 = "allogreffe_logo_footer.png"


os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_PDF_FOLDER, exist_ok=True)

# --- Basic Logging Setup (from first script) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s-%(levelname)s-%(filename)s:%(lineno)d - %(message)s')


# --- Helper & Initialization Functions (from second script, get_base64_image from first) ---
def init_session_state_key(key, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value

def reset_session_state():
    active_page = st.session_state.get('active_page', 'Nouveau Dossier')
    # Save sidebar state if needed, or other persistent states
    # For now, a simple clear and re-init
    st.session_state.clear()
    st.session_state.active_page = active_page
    initialize_all_form_keys() # Re-initialize form keys
    st.session_state.edit_mode = False
    logging.info("Form state has been reset for a new dossier.")

def initialize_all_form_keys():
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
    init_session_state_key('app_initialized', True) # Mark as initialized

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO(); img.save(buffer, format='PNG'); buffer.seek(0)
    return buffer

# --- get_base64_image from first script ---
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError: logging.warning(f"Logo file not found: {image_path}"); return None
    except Exception as e: logging.error(f"Error reading logo {image_path}: {e}"); return None

# --- PDF Generation (from second script - unchanged) ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            self.font_family = 'DejaVu'
        except RuntimeError:
            logging.warning("DejaVuSans.ttf not found. PDF may not render special characters correctly. Please download it and place it in the same folder as the script.")
            self.font_family = 'Arial' # Fallback font

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
            self.set_font(self.font_family, 'B' if status else '', 10) # Bold if status is True
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


# --- UI Specific Helpers (from first script) ---
def render_footer():
    logo_base64 = get_base64_image(LOGO_PATH)
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" alt="Logo" style="height: 45px; margin-bottom: 5px;">' if logo_base64 else ""
    # You might want to change "FM6SS" to your app's name or organization
    st.markdown(f"""<div style="border-top: 1px solid #e0e0e0; margin-top: 40px; padding-top: 15px; text-align: center;">{logo_html}<p style="font-size: 12px; color: #6c757d; margin-top: 5px;">© {datetime.datetime.now().year} - Gestion Allo-Greffe | <b>Votre Organisation</b></p></div>""", unsafe_allow_html=True)

# --- _inject_custom_styles from first script ---
def _inject_custom_styles():
    st.markdown("""<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background-color: #FFFFFF !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .main { background-color: #FFFFFF !important; padding-top: 1rem !important; padding-left: 2rem; padding-right: 2rem;} /* Add padding */
        .stApp > header { visibility: hidden; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .page-header { padding: 1.5rem 1rem; background: linear-gradient(135deg, #115e2a 0%, #1a803d 100%); color: white; border-radius: 10px; margin-bottom: 2rem; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
        .page-header h1 { margin: 0; font-size: 2.0rem; font-weight: 600; letter-spacing: 0.5px; display: flex; align-items: center; }
        .page-header h1 i { margin-right: 12px; font-size: 1.8rem; opacity: 0.9; }
        .page-header p { margin: 5px 0 0 0; opacity: 0.9; font-size: 0.95rem; }
        
        /* Styles for connection info - can be removed if not used by this app directly */
        .connection-info, .connection-info-disconnected { text-align: center; padding: 12px 15px; margin-bottom: 20px; border-radius: 8px; font-size: 0.95rem; font-weight: 500; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08); display: flex; align-items: center; justify-content: center; border-left: 5px solid transparent; }
        .connection-info { background-color: #e6f4ea; color: #1e8449; border-left-color: #2ecc71; }
        .connection-info-disconnected { background-color: #fdedec; color: #c0392b; border-left-color: #e74c3c; }
        .connection-info i, .connection-info-disconnected i { font-size: 1.3rem; margin-right: 10px; }
        .connection-info span, .connection-info-disconnected span { font-weight: 600; margin: 0 5px; }
        .connection-info-disconnected a { color: #c0392b; font-weight: bold; text-decoration: none; }
        .connection-info-disconnected a:hover { text-decoration: underline; }

        div[data-testid="stDateInput"] label, div[data-testid="stTextInput"] label, div[data-testid="stSelectbox"] label, div[data-testid="stTextArea"] label, div[data-testid="stRadio"] label, div[data-testid="stNumberInput"] label, div[data-testid="stFileUploader"] label { font-weight: 550; font-size: 0.9rem; color: #333;} /* Slightly smaller form labels */
        div[data-testid="stTabs"] button[role="tab"] { font-weight: 600; font-size: 1.0rem; padding: 0.7rem 1.3rem; border-bottom: 3px solid transparent; color: #495057;}
        div[data-testid="stTabs"] button[aria-selected="true"] { color: #115e2a; border-bottom-color: #115e2a !important; background-color: #f8f9fa;}
        div[data-testid="stAlert"] > div { border: none !important; border-radius: 6px; padding: 1rem; border-left: 4px solid; }
        div[data-testid="stAlert"][kind="success"] { background-color: #e6f4ea; color: #1e8449; border-left-color: #2ecc71; }
        div[data-testid="stAlert"][kind="info"] { background-color: #eaf2f8; color: #2980b9; border-left-color: #3498db; }
        div[data-testid="stAlert"][kind="warning"] { background-color: #fef9e7; color: #b9770e; border-left-color: #f39c12; }
        div[data-testid="stAlert"][kind="error"] { background-color: #fdedec; color: #c0392b; border-left-color: #e74c3c; }
        
        /* Metric styling - can be kept if you plan to add st.metric, or removed */
        div[data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #e0e0e0; border-radius: 10px; padding: 1.2rem 1rem; box-shadow: 0 2px 5px rgba(0,0,0,0.05); transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out; text-align: left; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }
        div[data-testid="stMetric"]:hover { transform: translateY(-4px); box-shadow: 0 4px 10px rgba(0,0,0,0.08); }
        div[data-testid="stMetric"] > label { font-size: 0.9rem; color: #555; font-weight: 500; margin-bottom: 0.5rem; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
        div[data-testid="stMetric"] > div[data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; color: #115e2a; line-height: 1.1; margin-bottom: 0.2rem; }
        div[data-testid="stMetric"] > div[data-testid="stMetricDelta"] { font-size: 0.9rem; font-weight: 600; }
        div[data-testid="stMetric"] > div[data-testid="stMetricDelta"] > div[data-testid="metric-delta-indicator"] { color: inherit !important; }
        div[data-testid="stMetric"] > div[data-testid="stMetricDelta"][data-delta-direction="increase"] { color: #28a745 !important; }
        div[data-testid="stMetric"] > div[data-testid="stMetricDelta"][data-delta-direction="decrease"] { color: #dc3545 !important; }

        div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] > button, form div[data-testid="stFormSubmitButton"] button { background: linear-gradient(135deg, #115e2a 0%, #1a803d 100%); color: white; border-radius: 6px; transition: transform 0.2s, box-shadow 0.2s, background 0.3s; border: none; padding: 0.6rem 1rem; font-weight: 500; font-size: 0.95rem; box-shadow: 0 2px 5px rgba(0,0,0,0.1); cursor: pointer; }
        div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] > button:hover, form div[data-testid="stFormSubmitButton"] button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); background: linear-gradient(135deg, #0f4a21 0%, #146630 100%); }
        div[data-testid="stButton"] button:focus, div[data-testid="stDownloadButton"] > button:focus, form div[data-testid="stFormSubmitButton"] button:focus { outline: none; box-shadow: 0 0 0 3px rgba(17, 94, 42, 0.3); }
        div[data-testid="stButton"] button:disabled, div[data-testid="stDownloadButton"] > button:disabled, form div[data-testid="stFormSubmitButton"] button:disabled { background: #cccccc !important; color: #666666 !important; cursor: not-allowed; box-shadow: none !important; transform: none !important; opacity: 0.7; }
        .divider { height: 1px; background: #e9ecef; margin: 2rem 0; border: none; }
        h3, h4, h5, h6 { color: #343a40; font-weight: 600; margin-bottom: 1rem; padding-bottom: 0.3rem; }
        h3 { font-size: 1.5rem; margin-top: 2.5rem; border-bottom: 1px solid #dee2e6; } /* For st.subheader */
        h4 { font-size: 1.3rem; margin-top: 2rem; display: flex; align-items: center;}
        h4 i { margin-right: 10px; color: #115e2a; font-size: 1.1em; }
        h5 { font-size: 1.1rem; margin-top: 1.5rem; color: #495057; font-weight: 600;}
        h6 { font-size: 1.0rem; margin-top: 1.0rem; color: #495057; font-weight: 550;}
        
        /* Sidebar Styles */
        div[data-testid="stSidebar"] { background-color: #f8f9fa !important; border-right: 1px solid #dee2e6; padding: 1.5rem 1rem; }
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] { background-color: inherit !important; }
        /* These will style streamlit_option_menu items */
        /* div[data-testid="stSidebar"] .nav-link { font-size: 0.95rem !important; display: flex; align-items: center; padding: 8px 12px !important; margin: 3px 0px !important; border-radius: 6px;} */
        /* div[data-testid="stSidebar"] .nav-link svg { font-size: 1.1rem !important; margin-right: 10px; width: 18px; text-align: center; } */
        /* div[data-testid="stSidebar"] .nav-link-selected { background-color: #115e2a !important; color: white !important; font-weight: 500 !important; } */
        /* div[data-testid="stSidebar"] .nav-link:not(.nav-link-selected):hover { background-color: #e9ecef; color: #333; } */
        
        /* DataFrame */
        div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #dee2e6; }
        div[data-testid="stDataFrame"] .col_heading { background-color: #f8f9fa; font-weight: 600; padding: 10px 8px; border-bottom: 1px solid #dee2e6; color: #343a40;}
        div[data-testid="stDataFrame"] .cell { padding: 8px; border-bottom: 1px solid #f1f1f1; }
        
        /* About Page specific - can be removed if no "About" page with this structure */
        .about-header { padding: 1.5rem 1rem; background: #fff; color: #333; border-radius: 10px; margin-bottom: 2rem; border: 1px solid #e0e0e0;}
        .about-header h1 { color: #115e2a;}
        .about-content.card { background: white; border-radius: 10px; padding: 2rem; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05); border: 1px solid #e0e0e0; font-size: 1rem; color: #343a40; line-height: 1.6; }

        /* Custom step navigation from Allo-Greffe app - may need adjustments */
        .step-navigation {
            display:flex;
            justify-content:center;
            align-items:center;
            flex-wrap:wrap;
            gap:10px;
            margin-bottom: 2rem;
            padding:1rem;
            background:#f8fafc; /* Light background to fit overall theme */
            border-radius:12px; /* Softer radius */
            border:1px solid #dee2e6; /* Consistent border */
        }
        .step-item{
            display:flex;align-items:center;margin:0 .5rem;padding:.5rem 1rem;border-radius:10px; /* Softer radius */
            font-weight:600;transition:all .3s ease; color: #495057; /* Default color */
        }
        .step-item.active{
            background:linear-gradient(135deg, #115e2a 0%, #1a803d 100%); /* Theme primary color */
            color:white;transform:scale(1.05);box-shadow:0 6px 12px rgba(17, 94, 42, 0.25); /* Theme shadow */
        }
        .step-item.completed{
            background:linear-gradient(135deg, #1abc9c 0%, #16a085 100%); /* Theme secondary/success color */
            color:white;
        }
        .step-item.inactive{
            background:#e9ecef; /* Lighter inactive state */
            color:#6c757d;
        }
        /* Styling for st.container(border=True) */
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stExpander"] > div[style*="border: 1px solid"] {
             border-radius: 8px !important; box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
        }
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] > div[data-testid="stMarkdownContainer"] > div[style*="border: 1px solid"],
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[style*="border: 1px solid"] { /* For direct containers */
            border-radius: 8px !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
            padding: 1rem !important; /* Add some padding */
            border: 1px solid #dee2e6 !important; /* Consistent border */
            background-color: #ffffff; /* Ensure white background */
        }


    </style>""", unsafe_allow_html=True)


def render_step_navigation():
    steps = [{"name": "Étape 1", "title": "Receveur", "icon": "fas fa-user-injured"}, {"name": "Étape 2", "title": "Donneur", "icon": "fas fa-user-friends"}, {"name": "Étape 3", "title": "Tribunaux", "icon": "fas fa-gavel"}, {"name": "Étape 4", "title": "Médical", "icon": "fas fa-file-medical-alt"}, {"name": "Étape 5", "title": "Ministère", "icon": "fas fa-landmark"}, {"name": "Étape 6", "title": "Organisme", "icon": "fas fa-hands-helping"}, {"name": "Étape 7", "title": "Confirmation", "icon": "fas fa-check-circle"}]
    current_step = st.session_state.current_step
    step_html = '<div class="step-navigation">'
    for i, step in enumerate(steps):
        status_class = "active" if i == current_step else ("completed" if i < current_step else "inactive")
        step_html += f'<div class="step-item {status_class}"><i class="{step["icon"]}" style="margin-right:8px;"></i><div><div style="font-size:0.8rem;opacity:0.8;">{step["name"]}</div><div style="font-size:0.9rem;">{step["title"]}</div></div></div>'
    st.markdown(step_html + '</div>', unsafe_allow_html=True)

def render_navigation_buttons():
    st.markdown("---") # This will be styled by .divider from the new CSS
    cols = st.columns([1, 1, 1, 1, 1]) # Consider 3 columns for prev/spacer/next
    # cols = st.columns([1,3,1])
    with cols[0]:
        if st.session_state.current_step > 0:
            if st.button("← Précédent", use_container_width=True): st.session_state.current_step -= 1; st.rerun()
    with cols[4]: # or cols[2] if using 3 columns
        if st.session_state.current_step < 6: # 6 is the last step index (Confirmation)
            if st.button("Suivant →", type="primary", use_container_width=True): st.session_state.current_step += 1; st.rerun()

# --- Page Renderers (Modified Headers) ---
def render_receveur_page():
    st.markdown('<div class="page-header"><h1><i class="fas fa-user-injured"></i> Informations sur le Receveur</h1><p>Détails personnels et administratifs du patient receveur.</p></div>', unsafe_allow_html=True)
    if st.session_state.edit_mode:
        st.info(f"**Mode Modification** | Vous modifiez le dossier du patient **{st.session_state.get('receveur_nom')} {st.session_state.get('receveur_prenom')}** (IPP: **{st.session_state.get('receveur_ipp')}**)")
        st.text_input("IPP", st.session_state.receveur_ipp, disabled=True)
    else:
        st.warning("⚠️ L'IPP est obligatoire et sera utilisé pour créer le dossier du patient.")
        st.session_state.receveur_ipp = st.text_input("IPP", st.session_state.receveur_ipp)

    with st.container(border=True):
        st.subheader("Détails du Receveur") # st.subheader will be styled by h3
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
    st.markdown('<div class="page-header"><h1><i class="fas fa-user-friends"></i> Informations sur le Donneur</h1><p>Détails personnels du donneur potentiel.</p></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Détails du Donneur")
        col1, col2 = st.columns(2)
        with col1: st.session_state.donneur_nom = st.text_input("Nom du Donneur", st.session_state.donneur_nom); st.session_state.donneur_prenom = st.text_input("Prénom du Donneur", st.session_state.donneur_prenom)
        with col2: st.session_state.donneur_date_naissance = st.date_input("Date de Naissance du Donneur", st.session_state.donneur_date_naissance); st.session_state.donneur_sexe = st.radio("Sexe du Donneur", ["Homme", "Femme"], index=["Homme", "Femme"].index(st.session_state.donneur_sexe), horizontal=True)
        # Add other donor fields if any, like groupage, address, contacts etc.
        # st.session_state.donneur_groupage = st.selectbox("Groupage Sanguin Donneur", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], index=["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].index(st.session_state.donneur_groupage))
        # st.session_state.donneur_adresse = st.text_area("Adresse Donneur", st.session_state.donneur_adresse, height=100)

def render_tribunaux_page():
    st.markdown('<div class="page-header"><h1><i class="fas fa-gavel"></i> Dossier Tribunal</h1><p>Suivi de l\'accord du tribunal et documents requis.</p></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Statut de l'Accord")
        st.session_state.accord_tribunal = st.selectbox("Statut de l'accord du Tribunal", ["En cours", "Accordé", "Refusé"], index=["En cours", "Accordé", "Refusé"].index(st.session_state.accord_tribunal))
    
    with st.container(border=True):
        st.subheader("Documents Administratifs Requis")
        if not st.session_state.receveur_ipp: st.error("Veuillez renseigner l'IPP du receveur à l'étape 1 pour joindre des fichiers."); return
        cols = st.columns(2)
        for i, doc in enumerate(ADMIN_DOCS_LIST):
            doc_key = f"admin_doc_{doc.lower().replace(' ', '_').replace('(', '').replace(')', '')}_upload"
            with cols[i % 2]:
                # Display existing file path or placeholder
                file_display_name = os.path.basename(st.session_state[doc_key]) if st.session_state.get(doc_key) and isinstance(st.session_state.get(doc_key), str) else "Aucun fichier"
                
                # Use an expander for cleaner UI if there's an existing file
                if st.session_state.get(doc_key) and isinstance(st.session_state.get(doc_key), str):
                    with st.expander(f"{doc} (Actuel: {file_display_name})", expanded=False):
                        st.caption(f"Chemin complet: {st.session_state[doc_key]}")
                        uploaded_file = st.file_uploader(f"Remplacer: {doc}", type=['pdf', 'jpg', 'png'], key=f"uploader_{doc_key}_replace")
                        if uploaded_file:
                            st.session_state[doc_key] = save_uploaded_file(uploaded_file, "tribunal")
                            st.rerun() # Rerun to update display
                else:
                    uploaded_file = st.file_uploader(f"Joindre: {doc}", type=['pdf', 'jpg', 'png'], key=f"uploader_{doc_key}_new")
                    if uploaded_file:
                        st.session_state[doc_key] = save_uploaded_file(uploaded_file, "tribunal")
                        st.rerun() # Rerun to update display
                # Simple display if no expander
                # if st.session_state.get(doc_key) and isinstance(st.session_state.get(doc_key), str):
                #    st.success(f"Fichier existant pour {doc}: '{os.path.basename(st.session_state[doc_key])}'")
                # uploaded_file = st.file_uploader(f"Joindre/Remplacer: {doc}", type=['pdf', 'jpg', 'png'], key=f"uploader_{doc_key}")
                # if uploaded_file:
                #    st.session_state[doc_key] = save_uploaded_file(uploaded_file, "tribunal")
                #    st.rerun()


def render_medical_page():
    st.markdown('<div class="page-header"><h1><i class="fas fa-file-medical-alt"></i> Dossier Médical</h1><p>Check-list des examens médicaux pré-greffe.</p></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Statut des Examens Médicaux")
        # Consider a more compact layout if many exams
        num_cols = 3 # Adjust as needed
        cols = st.columns(num_cols)
        for i, exam in enumerate(MEDICAL_EXAMS_LIST):
            exam_key = f"medical_exam_{exam.lower().replace(' ', '_').replace('é', 'e').replace('è', 'e')}"
            with cols[i % num_cols]:
                 st.checkbox(exam, value=st.session_state.get(exam_key, False), key=exam_key) # Assign key directly

def render_ministere_page():
    st.markdown('<div class="page-header"><h1><i class="fas fa-landmark"></i> Dossier Ministère</h1><p>Suivi de l\'accord du ministère et documents associés.</p></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Statut de l'Accord")
        st.session_state.accord_ministere = st.selectbox("Statut de l'accord du Ministère", ["En cours", "Accordé", "Refusé"], index=["En cours", "Accordé", "Refusé"].index(st.session_state.accord_ministere))
    
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
    st.markdown('<div class="page-header"><h1><i class="fas fa-hands-helping"></i> Dossier Organisme Payeur</h1><p>Suivi de l\'accord de l\'organisme payeur.</p></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("Accord de l'Organisme")
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
    st.markdown('<div class="page-header"><h1><i class="fas fa-check-circle"></i> Confirmation et Soumission</h1><p>Vérifiez les informations avant de finaliser le dossier.</p></div>', unsafe_allow_html=True)
    if st.session_state.edit_mode:
        st.info(f"Vous êtes sur le point de **mettre à jour** le dossier du patient **{st.session_state.get('receveur_nom')} {st.session_state.get('receveur_prenom')}**.")
    
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("📝 Récapitulatif Receveur", expanded=True):
            st.write(f"**IPP:** {st.session_state.get('receveur_ipp', 'N/A')}")
            st.write(f"**Nom Complet:** {st.session_state.get('receveur_nom', '')} {st.session_state.get('receveur_prenom', '')}")
            st.write(f"**Date de Naissance:** {st.session_state.get('receveur_date_naissance', datetime.date.today()).strftime('%d/%m/%Y')}")
            st.write(f"**Organisme:** {st.session_state.get('receveur_organisme', 'N/A')}")

        with st.expander("⚖️ Statuts des Accords", expanded=True):
            st.write(f"**Tribunal:** {st.session_state.get('accord_tribunal', 'N/A')}")
            st.write(f"**Ministère:** {st.session_state.get('accord_ministere', 'N/A')}")
            st.write(f"**Organisme:** {st.session_state.get('organisme_accord_statut', 'N/A')}")

    with col2:
        with st.expander("📝 Récapitulatif Donneur", expanded=True):
            st.write(f"**Nom Complet:** {st.session_state.get('donneur_nom', '')} {st.session_state.get('donneur_prenom', '')}")
            st.write(f"**Date de Naissance:** {st.session_state.get('donneur_date_naissance', datetime.date.today()).strftime('%d/%m/%Y')}")
        
        # QR Code for easy access/sharing - Example
        qr_data = f"IPP: {st.session_state.get('receveur_ipp', 'N/A')}\nPatient: {st.session_state.get('receveur_nom', '')} {st.session_state.get('receveur_prenom', '')}"
        qr_img_buffer = generate_qr_code(qr_data)
        st.image(qr_img_buffer, caption="QR Code du Dossier (Simplifié)", width=150)


    st.markdown("<hr class='divider'>", unsafe_allow_html=True) # Styled divider
    button_label = "Mettre à Jour le Dossier" if st.session_state.edit_mode else "Générer et Enregistrer le Dossier"
    if st.button(button_label, type="primary", use_container_width=True):
        if not st.session_state.receveur_ipp: st.error("L'IPP du receveur est obligatoire pour sauvegarder le dossier."); return
        patient_folder = os.path.join(BASE_UPLOAD_FOLDER, st.session_state.receveur_ipp); os.makedirs(patient_folder, exist_ok=True)
        data_to_save = {}
        # Filter session state items for saving
        for k, v in st.session_state.items():
            if k in ['app_initialized', 'current_step', 'active_page', 'edit_mode', 'search_query', 'search_by', 'search_results'] or k.startswith('uploader_') or k.startswith('FormSubmitter'):
                continue # Skip internal UI state variables and uploaders
            if isinstance(v, (datetime.date, datetime.datetime)): data_to_save[k] = v.isoformat()
            elif isinstance(v, (str, int, float, bool, list, dict)) or v is None: data_to_save[k] = v
            # else: logging.warning(f"Skipping non-serializable type for key {k}: {type(v)}")

        with open(os.path.join(patient_folder, "data.json"), 'w', encoding='utf-8') as f: json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        
        pdf_filename = os.path.join(GENERATED_PDF_FOLDER, f"Rapport_{st.session_state.receveur_ipp}.pdf")
        try:
            generate_pdf_report(st.session_state, pdf_filename) # Pass current session state
            st.success(f"Dossier pour le patient IPP `{st.session_state.receveur_ipp}` a été sauvegardé avec succès!"); st.balloons()
            with open(pdf_filename, "rb") as pdf_file:
                st.download_button(label="Télécharger le Rapport PDF", data=pdf_file, file_name=os.path.basename(pdf_filename), mime="application/octet-stream", use_container_width=True)
        except Exception as e:
            st.error(f"Erreur lors de la génération du PDF: {e}")
            logging.error(f"PDF generation error: {e}", exc_info=True)


def render_dashboard_page():
    st.markdown('<div class="page-header"><h1><i class="fas fa-tachometer-alt"></i> Tableau de Bord des Dossiers</h1><p>Vue d\'ensemble des dossiers patients enregistrés.</p></div>', unsafe_allow_html=True)
    dossiers = []
    if os.path.exists(BASE_UPLOAD_FOLDER):
        for ipp_folder_name in sorted(os.listdir(BASE_UPLOAD_FOLDER)):
            # Ensure it's a directory
            if not os.path.isdir(os.path.join(BASE_UPLOAD_FOLDER, ipp_folder_name)):
                continue
            json_path = os.path.join(BASE_UPLOAD_FOLDER, ipp_folder_name, "data.json")
            if os.path.isfile(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
                    dossiers.append({
                        "IPP": data.get("receveur_ipp", "N/A"),
                        "Nom Receveur": f"{data.get('receveur_nom', '')} {data.get('receveur_prenom', '')}".strip(),
                        "Accord Tribunal": data.get("accord_tribunal", "N/A"),
                        "Accord Ministère": data.get("accord_ministere", "N/A"),
                        "Nom Donneur": f"{data.get('donneur_nom', '')} {data.get('donneur_prenom', '')}".strip(),
                        "Date Création/Modif": datetime.datetime.fromtimestamp(os.path.getmtime(json_path)).strftime('%Y-%m-%d %H:%M') if os.path.exists(json_path) else "N/A"
                    })
                except json.JSONDecodeError: logging.error(f"Could not decode JSON for patient {ipp_folder_name}")
                except Exception as e: logging.error(f"Error processing folder {ipp_folder_name}: {e}")
    if not dossiers: st.info("Aucun dossier patient n'a été trouvé."); return
    df_dossiers = pd.DataFrame(dossiers)
    st.dataframe(df_dossiers, use_container_width=True, hide_index=True)


def search_for_patient(query, search_by):
    matches = []
    if not query: return matches
    query = query.lower().strip()
    if not os.path.exists(BASE_UPLOAD_FOLDER): return matches

    for ipp_folder_name in os.listdir(BASE_UPLOAD_FOLDER):
        if not os.path.isdir(os.path.join(BASE_UPLOAD_FOLDER, ipp_folder_name)):
            continue
        json_path = os.path.join(BASE_UPLOAD_FOLDER, ipp_folder_name, "data.json")
        if os.path.isfile(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    patient_ipp = data.get('receveur_ipp', '').lower()
                    patient_name = f"{data.get('receveur_nom', '')} {data.get('receveur_prenom', '')}".lower().strip()
                    
                    if (search_by == 'IPP' and query in patient_ipp) or \
                       (search_by == 'Nom' and query in patient_name):
                        matches.append({
                            'ipp': data.get('receveur_ipp', 'N/A'),
                            'name': f"{data.get('receveur_nom', '')} {data.get('receveur_prenom', '')}".strip()
                        })
                except (json.JSONDecodeError, KeyError):
                    logging.warning(f"Skipping folder {ipp_folder_name} due to data error.")
                    continue
    return matches

def load_patient_data(ipp_to_load):
    json_path = os.path.join(BASE_UPLOAD_FOLDER, ipp_to_load, "data.json")
    if not os.path.isfile(json_path):
        st.error(f"Fichier de données introuvable pour l'IPP {ipp_to_load}.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            st.error(f"Erreur de lecture du fichier de données pour l'IPP {ipp_to_load}.")
            return

    # Preserve active page, then clear and re-initialize specific form keys
    active_page_before_load = st.session_state.get('active_page') # Store current page
    
    # Selective reset: Reset only form-related keys
    # Keys to preserve across loads if they exist
    preserved_keys = {
        'active_page': active_page_before_load,
        'app_initialized': st.session_state.get('app_initialized', True),
        'search_query': st.session_state.get('search_query', ''), # Preserve search state
        'search_by': st.session_state.get('search_by', 'IPP'),
        'search_results': st.session_state.get('search_results', [])
    }

    st.session_state.clear() # Clear everything first
    initialize_all_form_keys() # Re-initialize all form keys to default

    # Restore preserved keys
    for pk, pv in preserved_keys.items():
        st.session_state[pk] = pv
        
    # Load data from JSON
    for key, value in data.items():
        if key in st.session_state: # Only update if key is part of our initialized form
            if isinstance(st.session_state[key], datetime.date) and isinstance(value, str):
                try:
                    st.session_state[key] = datetime.datetime.strptime(value, '%Y-%m-%d').date()
                except ValueError:
                    try: # Handle full ISO format if present
                        st.session_state[key] = datetime.datetime.fromisoformat(value).date()
                    except ValueError:
                        logging.warning(f"Could not parse date string '{value}' for key '{key}'. Keeping default.")
                        # Keep default if parsing fails
            else:
                st.session_state[key] = value
        # else:
            # logging.warning(f"Key '{key}' from JSON not found in initialized session state. Skipping.")

    st.session_state.active_page = "Nouveau Dossier" # Navigate to form
    st.session_state.edit_mode = True
    st.session_state.current_step = 0 # Start at the first step of the form
    st.session_state.receveur_ipp = ipp_to_load # Ensure IPP is correctly set for edit mode
    st.rerun()


def render_search_page():
    st.markdown('<div class="page-header"><h1><i class="fas fa-search"></i> Rechercher / Modifier un Dossier</h1><p>Trouver et éditer des dossiers patients existants.</p></div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.subheader("Critères de Recherche")
        col1, col2 = st.columns([3,1])
        with col1: st.session_state.search_query = st.text_input("Rechercher un patient", st.session_state.get('search_query',''), placeholder="Entrez un IPP ou un nom...")
        with col2: st.session_state.search_by = st.selectbox("Rechercher par", ["IPP", "Nom"], index=["IPP", "Nom"].index(st.session_state.get('search_by','IPP')))
        
        if st.button("Lancer la recherche", type="primary", use_container_width=True):
            st.session_state.search_results = search_for_patient(st.session_state.search_query, st.session_state.search_by)
            if not st.session_state.search_results and st.session_state.search_query:
                st.info("Aucun dossier correspondant à votre recherche n'a été trouvé.")
            elif not st.session_state.search_query:
                st.warning("Veuillez entrer un terme de recherche.")


    if st.session_state.get('search_results'):
        st.markdown("---") # Styled divider
        st.subheader(f"Résultats de la Recherche ({len(st.session_state.search_results)} trouvé(s))")
        for patient in st.session_state.search_results:
            with st.container(border=True): # Each result in a styled container
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**Nom:** {patient['name']}<br>**IPP:** {patient['ipp']}", unsafe_allow_html=True)
                if c2.button("Modifier ce dossier", key=f"load_{patient['ipp']}", use_container_width=True):
                    load_patient_data(patient['ipp']) # This will trigger a rerun


# --- Main Application ---
def main():
    # Page Config (once at the top)
    st.set_page_config(
        page_title="Gestion Allo-Greffe",
        page_icon="👨‍⚕️", # or your preferred icon
        layout="wide",
        initial_sidebar_state="expanded"
    )
    _inject_custom_styles() # Apply custom CSS globally

    # Initialize session state if not already done
    if 'app_initialized' not in st.session_state:
        initialize_all_form_keys() # This now sets 'app_initialized'
        st.session_state.active_page = 'Nouveau Dossier' # Default page
        logging.info("Main app: Session state initialized for the first time.")


    with st.sidebar:
        # Sidebar Logo (from first script's style)
        logo_base64_sidebar = get_base64_image(LOGO_PATH_2) # LOGO_PATH_2 from first script
        if logo_base64_sidebar:
            st.markdown(f'<div style="text-align: center; padding-bottom: 1rem;"><img src="data:image/png;base64,{logo_base64_sidebar}" alt="Logo App" style="height: 55px;"></div>', unsafe_allow_html=True)
        else: # Fallback title if logo not found
            st.markdown("<h2 style='text-align: center;'>Gestion Allo-Greffe</h2>", unsafe_allow_html=True)
        
        st.markdown("---") # Divider

        page_options = ["Nouveau Dossier", "Rechercher / Modifier", "Tableau de Bord"]
        page_icons = ["plus-square-fill", "search", "bar-chart-fill"] # Bootstrap Icons

        try:
            default_index = page_options.index(st.session_state.active_page)
        except (ValueError, KeyError): # Handle case where active_page might not be in options
            default_index = 0
            st.session_state.active_page = page_options[0]


        selected_page = option_menu(
            menu_title=None,  # Hides the default menu title if "" or None
            options=page_options,
            icons=page_icons,
            menu_icon="cast", # Main menu icon
            default_index=default_index,
            # Styles from the first script's option_menu
            styles={
                "container": {"padding": "0!important", "background-color": "#f8f9fa"}, # Matches sidebar bg
                "icon": {"color": "#115e2a", "font-size": "1.1rem"}, # Theme color for icons
                "nav-link": {"font-size": "0.95rem", "text-align": "left", "margin":"3px", "padding":"8px 15px", "--hover-color": "#e9ecef"},
                "nav-link-selected": {"background-color": "#115e2a", "color": "white", "font-weight": "500"},
            }
        )

        if selected_page != st.session_state.active_page:
            st.session_state.active_page = selected_page
            if selected_page == "Nouveau Dossier" and st.session_state.get('edit_mode', False) == False: # Only reset if not in edit mode when switching to Nouveau Dossier
                reset_session_state() # Resets form for a truly new dossier
            st.rerun()

        st.markdown("---")
        # Footer logo in sidebar (optional, can use your app's specific logo)
        # For this example, let's use the same logo as the main footer or a different one
        # sidebar_footer_logo = get_base64_image(LOGO_PATH) # or a different logo
        # if sidebar_footer_logo:
        #    st.markdown(f'<div style="text-align: center; padding: 1rem;"><img src="data:image/png;base64,{sidebar_footer_logo}" width="100"></div>', unsafe_allow_html=True)


    # --- Page Routing ---
    if st.session_state.active_page == "Nouveau Dossier":
        render_step_navigation()
        page_renderers = [render_receveur_page, render_donneur_page, render_tribunaux_page, render_medical_page, render_ministere_page, render_organisme_page, render_confirmation_page]
        # Ensure current_step is valid
        current_step = st.session_state.get('current_step', 0)
        if 0 <= current_step < len(page_renderers):
            page_renderers[current_step]()
        else:
            st.error("Étape invalide. Réinitialisation à la première étape.")
            st.session_state.current_step = 0
            page_renderers[0]()

        if current_step < len(page_renderers) -1: # Don't show nav buttons on confirmation page
            render_navigation_buttons()
    elif st.session_state.active_page == "Tableau de Bord":
        render_dashboard_page()
    elif st.session_state.active_page == "Rechercher / Modifier":
        render_search_page()

    render_footer() # Add the footer to all pages

if __name__ == "__main__":
    main()
