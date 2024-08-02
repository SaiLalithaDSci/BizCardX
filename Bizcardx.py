import streamlit as st
import easyocr
from PIL import Image, ImageDraw
import numpy as np
import re
import pandas as pd
from sqlalchemy import create_engine, types
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# ===================================================   /   /   Dash Board   /   /   ======================================================== #

# Configuring Streamlit GUI 
st.set_page_config(layout='wide')

# Title
st.title(':blue[Business Card Data Extraction]')

# Tabs 
tab1, tab2, tab3 = st.tabs(["Data Extraction zone", "Data modification zone", "Data Frame Display"])

# ==========================================   /   /   Data Extraction and upload zone   /   /   ============================================== #

with tab1:
    st.subheader(':red[Data Extraction]')

    # Image file uploaded
    import_image = st.file_uploader('**Select a business card (Image file)**', type=['png', 'jpg', "jpeg"], accept_multiple_files=False)

    # Note
    st.markdown('''File extension support: **PNG, JPG, TIFF**, File size limit: **2 Mb**, Image dimension limit: **1500 pixel**, Language: **English**.''')

    # --------------------------------      /   Extraction process   /     ---------------------------------- #

    if import_image is not None:
        try:
            # Create the reader object with desired languages
            reader = easyocr.Reader(['en'], gpu=False)
        except:
            st.info("Error: easyocr module is not installed. Please install it.")

        try:
            # Read the image file as a PIL Image object
            if isinstance(import_image, str):
                image = Image.open(import_image)
            elif isinstance(import_image, Image.Image):
                image = import_image
            else:
                image = Image.open(import_image)

            image_array = np.array(image)
            text_read = reader.readtext(image_array)

            result = []
            for text in text_read:
                result.append(text[1])

        except:
            st.info("Error: Failed to process the image. Please try again with a different image.")

        # -------------------------      /   Display the processed card with yellow box   /     ---------------------- #

        col1, col2 = st.columns(2)

        with col1:
            # Define a function to draw the box on image
            def draw_boxes(image, text_read, color='yellow', width=2):
                # Create a new image with bounding boxes
                image_with_boxes = image.copy()
                draw = ImageDraw.Draw(image_with_boxes)
                
                # Draw boundaries
                for bound in text_read:
                    p0, p1, p2, p3 = bound[0]
                    draw.line([*p0, *p1, *p2, *p3, *p0], fill=color, width=width)
                return image_with_boxes

            # Function calling
            result_image = draw_boxes(image, text_read)

            # Result image
            st.image(result_image, caption='Captured text')

        # ----------------------------    /     Data processing and converted into data frame   /   ------------------ #

        with col2:
            # Initialize the data dictionary
            data = {
                "Company_name": [],
                "Card_holder": [],
                "Designation": [],
                "Mobile_number": [],
                "Email": [],
                "Website": [],
                "Area": [],
                "City": [],
                "State": [],
                "Pin_code": [],
            }

            # Define function
            def get_data(res):
                city = ""  # Initialize the city variable
                for ind, i in enumerate(res):
                    # To get WEBSITE_URL
                    if "www " in i.lower() or "www." in i.lower():
                        data["Website"].append(i)
                    elif "WWW" in i:
                        data["Website"].append(res[ind-1] + "." + res[ind])

                    # To get EMAIL ID
                    elif "@" in i:
                        data["Email"].append(i)

                    # To get MOBILE NUMBER
                    elif "-" in i:
                        data["Mobile_number"].append(i)
                        if len(data["Mobile_number"]) == 2:
                            data["Mobile_number"] = " & ".join(data["Mobile_number"])

                    # To get COMPANY NAME
                    elif ind == len(res) - 1:
                        data["Company_name"].append(i)

                    # To get CARD HOLDER NAME
                    elif ind == 0:
                        data["Card_holder"].append(i)

                    # To get DESIGNATION
                    elif ind == 1:
                        data["Designation"].append(i)

                    # To get AREA
                    if re.findall("^[0-9].+, [a-zA-Z]+", i):
                        data["Area"].append(i.split(",")[0])
                    elif re.findall("[0-9] [a-zA-Z]+", i):
                        data["Area"].append(i)

                    # To get CITY NAME
                    match1 = re.findall(".+St , ([a-zA-Z]+).+", i)
                    match2 = re.findall(".+St,, ([a-zA-Z]+).+", i)
                    match3 = re.findall("^[E].*", i)
                    if match1:
                        city = match1[0]  # Assign the matched city value
                    elif match2:
                        city = match2[0]  # Assign the matched city value
                    elif match3:
                        city = match3[0]  # Assign the matched city value

                    # To get STATE
                    state_match = re.findall("[a-zA-Z]{9} +[0-9]", i)
                    if state_match:
                        data["State"].append(i[:9])
                    elif re.findall("^[0-9].+, ([a-zA-Z]+);", i):
                        data["State"].append(i.split()[-1])
                    if len(data["State"]) == 2:
                        data["State"].pop(0)

                    # To get PINCODE
                    if len(i) >= 6 and i.isdigit():
                        data["Pin_code"].append(i)
                    elif re.findall("[a-zA-Z]{9} +[0-9]", i):
                        data["Pin_code"].append(i[10:])

                data["City"].append(city)  # Append the city value to the 'city' array
                
            # Call function
            get_data(result)

            # Create dataframe
            data_df = pd.DataFrame(data)

            # Show dataframe
            st.dataframe(data_df.T)

        # --------------------------------------   /   Data Upload to PostgreSQL   /   --------------------------------------- #

        # Create a session state object
        class SessionState:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        session_state = SessionState(data_uploaded=False)

        # Upload button
        st.write('Click the :red[**Upload to PostgreSQL DB**] button to upload the data')
        Upload = st.button('**Upload to PostgreSQL DB**', key='upload_button')

        # Check if the button is clicked
        if Upload:
            session_state.data_uploaded = True

        # Execute the program if the button is clicked
        if session_state.data_uploaded:
            # Connect to the PostgreSQL server
            conn = psycopg2.connect(
                host="localhost",
                user="postgres",
                password="password",
                dbname="bizcard_db",
                port="5432")

            conn.autocommit = True
            cur = conn.cursor()

            # Connect to the newly created database
            engine = create_engine('postgresql+psycopg2://postgres:password@localhost/bizcard_db', echo=False)
            conn = psycopg2.connect(
                host="localhost",
                user="postgres",
                password="password",
                dbname="bizcard_db",
                port="5432")
            cur = conn.cursor()

            try:
                # Use pandas to insert the DataFrame data into the SQL Database table
                data_df.to_sql('bizcardx_data', engine, if_exists='append', index=False, dtype={
                    "Company_name": types.VARCHAR(length=225),
                    "Card_holder": types.VARCHAR(length=225),
                    "Designation": types.VARCHAR(length=225),
                    "Mobile_number": types.VARCHAR(length=50),
                    "Email": types.TEXT,
                    "Website": types.TEXT,
                    "Area": types.VARCHAR(length=225),
                    "City": types.VARCHAR(length=225),
                    "State": types.VARCHAR(length=225),
                    "Pin_code": types.VARCHAR(length=10)})
                
                # Upload completed message
                st.info('Data Successfully Uploaded')

            except:
                st.info("Card data already exists")

            conn.close()

            # Reset the session state after executing the program
            session_state.data_uploaded = False

    else:
        st.info('Click the Browse file button and upload an image')

# =================================================   /   /   Modification zone   /   /   ==================================================== #

with tab2:

    col1, col2 = st.columns(2)

    # ------------------------------   /   /   Edit option   /   /   -------------------------------------------- #

    with col1:
        st.subheader(':red[Edit option]')
        conn = psycopg2.connect(
                host="localhost",
                user="postgres",
                password="password",
                dbname="bizcard_db",
                port="5432")

        if conn:
            try:

                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                cur = conn.cursor()

                # Execute the query to retrieve the cardholder data
                cur.execute('SELECT "Card_holder" FROM bizcardx_data')

                # Fetch the cardholder data from the query result
                Card_holders = [row[0] for row in cur.fetchall()]
                st.write(f"Card holders fetched: {Card_holders}")

                

                # Displaying the options for card holders
                if Card_holders:
                    card_holder_name = st.selectbox('Select the card holder name you want to modify', Card_holders)
                    new_value = st.text_input('Enter the new value')

                    # Select the column to be updated
                    options = ["Company_name", "Card_holder", "Designation", "Mobile_number", "Email", "Website", "Area", "City", "State", "Pin_code"]
                    column = st.selectbox('Select the column to be updated', options)

                    # Update the column with the new value
                    if st.button('Update'):
                        
                        if conn:
                            cur = conn.cursor()
                            query = sql.SQL('UPDATE bizcardx_data SET {column} = %s WHERE "Card_holder" = %s').format(
                                column=sql.Identifier(column))
                            cur.execute(query, (new_value, card_holder_name))

                            conn.commit()
                            

                            st.success('Value updated successfully')
                            conn.close()
                        else:
                            st.error("Failed to reconnect to the database for updating.")

                else:
                    st.info("No card holder data found in the database")

            except psycopg2.Error as e:
                st.error(f"Database error: {e}")
            except Exception as e:
                st.error(f"Error: {e}")

    # -------------------------------   /   /   Delete option   /   /   -------------------------------------------- #

    with col2:
        st.subheader(':red[Delete option]')

        conn = psycopg2.connect(
                host="localhost",
                user="postgres",
                password="password",
                dbname="bizcard_db",
                port="5432")
        
        if conn:
            try:

                cur = conn.cursor()

                # Execute the query to retrieve the cardholder data
                cur.execute('SELECT "Card_holder" FROM bizcardx_data')

                # Fetch the cardholder data from the query result
                Card_holders = [row[0] for row in cur.fetchall()]
                st.write(f"Card holders fetched: {Card_holders}")

                # Displaying the options for card holders
                if Card_holders:
                    card_holder_name = st.selectbox('Select the card holder name you want to delete', Card_holders)

                    # Delete the row
                    if st.button('Delete'):
                        
                        if conn:
                            cur = conn.cursor()
                            cur.execute('DELETE FROM bizcardx_data WHERE "Card_holder" = %s', (card_holder_name,))
                            conn.commit()
                            
                            st.success('Value deleted successfully')
                        else:
                            st.error("Failed to reconnect to the database for deleting.")
                            conn.close()
                else:
                    st.info("No card holder data found in the database")

            except psycopg2.Error as e:
                st.error(f"Database error: {e}")
            except Exception as e:
                st.error(f"Error: {e}")

# -------------------------------   /   /   Data Frame Display   /   /   -------------------------------------------- #

with tab3:
    st.subheader(':red[Data Frame]')
    conn = psycopg2.connect(
            host="localhost",
            user="postgres",
            password="password",
            dbname="bizcard_db",
            port="5432")

    if conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT * FROM bizcardx_data')
            rows = cur.fetchall()
            

            if rows:
                df = pd.DataFrame(rows, columns=["Company_name", "Card_holder", "Designation", "Mobile_number", "Email", "Website", "Area", "City", "State", "Pin_code"])
                st.dataframe(df)
            else:
                st.info("No data found in the database.")
                conn.close()

        except psycopg2.Error as e:
            st.error(f"Database error: {e}")
        except Exception as e:
            st.error(f"Error: {e}")
