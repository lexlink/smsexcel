from flask import Flask, render_template, request, redirect, session, url_for, flash
import pandas as pd
from sms_send import send_sms_sender, check_delivery_reports, check_delivery_against_api
import asyncio
from database import get_database,transfer_records, archived_records

app = Flask(__name__)
collection = get_database()

app.secret_key = 'your_secret_key'
app.config['RESULTS_PER_PAGE'] = 18  # Number of records to display per page


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            print("File received:", file.filename)

            data = pd.read_excel(file)
            print(data.head())

            # Check if the required column names are present in the Excel file
            if 'Phone Number' not in data.columns or 'Amount to Pay' not in data.columns:
                return "Missing column(s) in the Excel file. Please ensure the file contains" \
                       " 'Phone Number' and 'Amount to Pay' columns."

            # Ensure 'Phone Number' column is of string data type
            data['Phone Number'] = data['Phone Number'].astype(str)
            print(data['Phone Number'])
            # Loop through the 'Phone Number' column to check for whitespaces
            has_whitespaces = any(data['Phone Number'].str.contains(' '))
            has_float = any(data['Phone Number'].str.contains('.0'))
            # If whitespaces are present, convert 'Phone Number' to string and remove whitespaces
            if has_float:
                data['Phone Number'] = data['Phone Number'].astype(str).str.replace('.0', '')
            if has_whitespaces:
                data['Phone Number'] = data['Phone Number'].str.replace(' ', '')
            
            # Drop non-finite values from 'Amount to Pay' column (e.g., NaN or inf)
            data = data.dropna(subset=['Amount to Pay'])

            # Round 'Amount to Pay' to integers (assuming it represents amounts in whole numbers)
            data['Amount to Pay'] = data['Amount to Pay'].astype(float)

            # Filter and process the data
            filtered_data = data[(data['Phone Number'].str.len() == 9) & (data['Phone Number'] != '0') & (data['Amount to Pay'] >= 1)]

            records = filtered_data[['Phone Number', 'Amount to Pay']].values.tolist()
            print(records)
            total_records = len(records)

            # Store data in session
            session['records'] = records
            session['total_records'] = total_records

            return redirect('/results')
        else:
            return "Invalid file format. Please upload an Excel file (.xlsx)."
    return render_template('upload.html')


@app.route('/results')
def show_results():
    # Retrieve data from session
    records = session.get('records')
    total_records = session.get('total_records')

    if records is None or total_records is None:
        return redirect('/')

    page = request.args.get('page', 1, type=int)
    results_per_page = app.config['RESULTS_PER_PAGE']
    start_index = (page - 1) * results_per_page
    end_index = start_index + results_per_page
    paginated_records = records[start_index:end_index]

    return render_template('results.html', records=paginated_records, total_records=total_records, page=page, results_per_page=results_per_page)


@app.route('/next-stage', methods=['GET', 'POST'])
def next_stage():
    # Retrieve data from session
    records = session.get('records')

    if records is None:
        return redirect('/')

    if request.method == 'POST':
        # Retrieve input message from the form submission
        message = request.form.get('text_input')

        # Store the input message in the session
        session['message'] = message

        return redirect('/last-stage')

    return render_template('next-stage.html', records=records)


@app.route('/last-stage', methods=['GET', 'POST'])
def last_stage():
    # Retrieve input text from the form
    input_text = request.form.get('input_text')

    # Retrieve records from the session
    records = session.get('records')
    if records is None:
        return redirect('/')

    # Apply the new_string operation for each record
    new_records = []
    for record in records:
        new_string = input_text.replace("tanxa", str(record[1]))
        new_records.append((record[0], new_string))
    return render_template('last-stage.html', input_text=input_text, records=new_records)


# Define the maximum number of concurrent requests
MAX_CONCURRENT_REQUESTS = 100

@app.route('/send-sms', methods=['GET', 'POST'])
def send_sms():
    if request.method == 'POST':
        records = request.form.getlist('new_records[]')
        responses = []

        async def send_sms_async():
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
            tasks = []

            async def send_sms_task(number, text):
                async with semaphore:
                    response = await send_sms_sender(number, text)
                    responses.append(response)

            for record in records:
                number, text = record.split(',', 1)
                task = asyncio.create_task(send_sms_task(number, text))
                tasks.append(task)
                print(f"Sending SMS: Number: {number}, Text: {text}")

            await asyncio.gather(*tasks)

        asyncio.run(send_sms_async())

        flash('Please wait while we transfer you to success', 'info')
        return redirect(url_for('success', responses=responses))

    return render_template('sms-send.html')


@app.route('/success')
def success():
    # Retrieve data from MongoDB collection
    data = list(collection.find().sort('_id', -1))
    total_records = collection.count_documents({})

    return render_template('success.html', data=data, total_records=total_records)


@app.route('/delete-all', methods=['POST'])
def delete_all():
    collection.delete_many({})  # Delete all documents in the collection
    return redirect(url_for('success'))


@app.route('/delete-all-archive', methods=['POST'])
def delete_all_archive():
    collection = archived_records()  # Assign the collection returned by archived_records() to a variable
    if collection is not None:
        collection.delete_many({})  # Delete all documents in the collection
    return redirect('/archive')

@app.route('/archive-records', methods=['POST'])
def archive_records():
    transfer_records()  # Call the function to archive the records
    flash("Records archived successfully.")
    return redirect(url_for('success'))


@app.route('/archive', methods=['GET'])
def see_archive():
    collection = archived_records()  # Call the function to retrieve the archived records
    if collection is not None:
        records = list(collection.find())
        total_records = collection.count_documents({})
        return render_template('archive.html', records=records, total_records=total_records)
    else:
        return render_template('archive.html', records=None, total_records=None)


# Route for the "/check-delivery-reports" endpoint
@app.route('/check-delivery-reports', methods=['POST', 'GET'])
def check_delivery_route():
    # Call the check_delivery_reports function asynchronously
    asyncio.run(check_delivery_reports())

    # Redirect back to the success page
    return redirect('/success')

@app.route('/check-delivery-api', methods=['POST', 'GET'])
def check_delivery_api():
    # Call the check_delivery_reports function asynchronously
    asyncio.run(check_delivery_against_api())

    # Redirect back to the success page
    return redirect('/success')


if __name__ == '__main__':
    app.run(debug=True)
