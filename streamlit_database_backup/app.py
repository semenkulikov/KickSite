import streamlit as st
import os

# Define the path to the database file
DATABASE_PATH = 'database/db.sqlite3'

# Ensure the database directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
if not os.path.exists(DATABASE_PATH):
    with open(DATABASE_PATH, 'w') as file:
        pass  # Create an empty file
# Function to download the database file
def download_database():
    with open(DATABASE_PATH, 'rb') as file:
        st.download_button(
            label="Download Database",
            data=file,
            file_name='db.sqlite3',
            mime='application/octet-stream'
        )

# Function to upload a new database file
def upload_database(uploaded_file):
    with open(DATABASE_PATH, 'wb') as file:
        file.write(uploaded_file.getbuffer())
    st.success("Database file has been uploaded and replaced successfully.")

# Streamlit app
st.title("Database Backup Manager")

st.header("Download Current Database")
download_database()

st.header("Upload New Database")
uploaded_file = st.file_uploader("Choose a file", type=["sqlite3"])

if uploaded_file is not None:
    upload_database(uploaded_file)