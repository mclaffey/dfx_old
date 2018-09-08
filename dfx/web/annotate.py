import shelve
import random
import string
import os


from flask import Flask, request, redirect, url_for, render_template, g, session, jsonify, Blueprint

annotate_bp = Blueprint('annotate', '__name__', url_prefix='/annotate')

#app = Flask(__name__)
#app.secret_key = '7efc472edc59865db258370035d0e5336c7db1a54f9748a1'


def get_db():
	return BlurbStore()

@annotate_bp.route('/')
def index():
	db = get_db()
	#return render_template('home.html', addresses = db.addresses())
	return render_template('annotate/home.html', previews = db.previews())

@annotate_bp.route('/create', methods=['GET', 'POST'])
def create():
	if request.method == 'GET':
		return """
			<form action="/create" method="POST">
				<label for="address">Address:</label>
				<input type="text" name="address" placeholder="address?" />
				<br/>
				<textarea name="content" rows=10 cols=80></textarea>
				<br />
				<input type="submit" />
			</form>	

			"""
	if request.method == 'POST':
		blurb = Blurb(str(request.form['address']), request.form['content'])
		db = get_db()
		db.put(blurb)
		return redirect(url_for('view', address=blurb.address))

@annotate_bp.route('/view/<string:address>')
def view(address):
	db = get_db()
	blurb = db.get_with_references(str(address))
	available_addresses = [_ for _ in db.addresses() if _ != str(address)]
	g.enumerate = enumerate
	return render_template("blurb.html", blurb=blurb, available_addresses=available_addresses)

@annotate_bp.route('/modify', methods=['POST'])
def modify():
	db = get_db()
	if 'new-address' in request.form:
		old_address = str(request.form['address'])
		new_address = str(request.form['new-address'])
		db.change_address(old_address, new_address)

		# if the session referred to the old address, update it
		if session.get('current_blurb_address', None) == old_address:
			session['current_blurb_address'] = new_address

		return jsonify(dict(
			status="success",
			url=url_for('view', address = request.form['new-address']),
			))
	if 'new-content' in request.form:
		blurb = db.get(str(request.form['address']))
		blurb.content = request.form['new-content']
		db.put(blurb)
		return jsonify(dict(status="success"))

@annotate_bp.route('/add-reference', methods=["POST"])
def add_reference():
	db = get_db()
	address = str(request.form['address'])
	blurb = db.get(address)
	new_ref_address = str(request.form['new-reference'])
	try:
		ref = db.get(new_ref_address)
	except KeyError:
		return jsonify({'status': 'fail', 'message': "Could not find reference to " + new_ref_address})

	insert_index = request.form.get('insert-index')
	if insert_index is None:
		insert_index = len(blurb.ref_list)
	else:
		insert_index = int(insert_index)

	blurb.ref_list.insert(insert_index, new_ref_address)
	db.put(blurb)
	sub_blurb_html = render_template("sub-blurb.html", blurb=blurb, ref=ref, i=0)
	return jsonify({'status': 'success', 'html': sub_blurb_html})

@annotate_bp.route('/remove-reference', methods=["POST"])
def remove_reference():
	db = get_db()
	address = str(request.form['parent-address'])
	blurb = db.get(address)
	delete_ref_address = str(request.form['ref-address-to-delete'])
	blurb.ref_list.remove(delete_ref_address)
	db.put(blurb)
	return jsonify({'status': 'success'})

@annotate_bp.route('/move-reference', methods=["POST"])
def move_reference():
	db = get_db()
	address = str(request.form['parent-address'])
	blurb = db.get(address)
	move_ref_address = str(request.form['ref-address-to-move'])
	current_index = blurb.ref_list.index(move_ref_address)
	destination_index = int(request.form['move-to-index']) - 1
	if current_index != destination_index:
		blurb.ref_list.pop(current_index)
		blurb.ref_list.insert(destination_index, move_ref_address)
		db.put(blurb)
	return redirect(url_for('view', address=blurb.address))

@annotate_bp.route('/example')
def example():
	return render_template('example.html')

@annotate_bp.route('/add_to_current', methods=['POST'])
# def add_to_current():
# 	"""Add content as a reference from the current blurb

# 	The current blurb is an address stored in a session variable. If none is
# 	available, a new one is created.
# 	"""
# 	db = get_db()

# 	# get current blurb
# 	current_blurb_address = session.get('current_blurb_address', None)	
# 	if current_blurb_address is None:
# 		current_blurb = Blurb(random_address(), 'Auto created as current blurb')
# 		db.put(current_blurb)
# 		session['current_blurb_address'] = current_blurb.address
# 	else:
# 		current_blurb = db.get(current_blurb_address)

# 	# create new incrementatl blurb
# 	blurb = Blurb(random_address(), request.form['content'])
# 	db.put(blurb)

# 	# add to current
# 	current_blurb.ref_list.append(blurb.address)
# 	db.put(current_blurb)

# 	return redirect(url_for('view', address=current_blurb.address))

@annotate_bp.route('/add_to_current')
def add_to_current():
	"""Add content as a reference from the current blurb

	The current blurb is an address stored in a session variable. If none is
	available, a new one is created.
	"""
	db = get_db()

	# get current blurb
	current_blurb_address = session.get('current_blurb_address', None)	
	if current_blurb_address is None:
		address = "main-" + random_address()
		current_blurb = Blurb(address, 'Auto created as current blurb')
		db.put(current_blurb)
		session['current_blurb_address'] = current_blurb.address
	else:
		current_blurb = db.get(current_blurb_address)

	# create new incremental blurb
	blurb = Blurb(random_address(), request.args.get('content'))
	db.put(blurb)

	# add to current
	current_blurb.ref_list.append(blurb.address)
	db.put(current_blurb)

	return jsonify(blurb.address)



@annotate_bp.route('/restart')
def restart():
	session.clear()
	os.remove('BlurbStore.shelve')
	return redirect(url_for('.index'))

class Blurb(object):
	def __init__(self, address, content, ref_list = []):
		if type(address) != str:
			raise ValueError('address must be string')
		self.address = address
		self.content = content
		self.ref_list = ref_list
	def __str__(self):
		return self.address + ": " + self.content

class BlurbStore(object):
	def __init__(self):
		# make sure we can initialize the object
		shelve.open('BlurbStore.shelve', flag='c')

	def put(self, blurb):
		s = shelve.open('BlurbStore.shelve', flag='c')
		s[blurb.address] = blurb

	def get(self, address):
		s = shelve.open('BlurbStore.shelve', flag='r')
		return s[address]

	def remove(self, address):
		s = shelve.open('BlurbStore.shelve', flag='c')
		del s[address]

	def addresses(self):
		"""Return a list of all keys
		"""
		s = shelve.open('BlurbStore.shelve', flag='r')
		return s.keys()

	def previews(self):
		"""Return a list of (address, content)
		"""
		s = shelve.open('BlurbStore.shelve', flag='r')
		previews = []
		keys = s.keys()
		for key in keys:
			blurb = s[key]
			previews.append((key, blurb.content))
		return previews


	def get_with_references(self, address):
		blurb = self.get(address)
		blurb.ref_list_resolved = []
		for ref_address in blurb.ref_list:
			try:
				blurb.ref_list_resolved.append(self.get(ref_address))
			except KeyError:
				missing_blurb = Blurb(ref_address, "Blurb address not found")
				blurb.ref_list_resolved.append(missing_blurb)
		return blurb

	def change_address(self, old_address, new_address):
		blurb = self.get(old_address)
		blurb.address = new_address
		self.put(blurb)
		self.remove(old_address)

		# iterate over all other blurbs in the store and change references if necessary
		for address in self.addresses():
			other_blurb = self.get(address)
			if old_address in other_blurb.ref_list:
				other_blurb.ref_list = [new_address if other_blurb_ref == old_address else other_blurb_ref for other_blurb_ref in other_blurb.ref_list]
				self.put(other_blurb)

def random_address():
	return 'blurb-' + ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))

