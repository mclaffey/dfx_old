import shelve
import random
import string
import os
import sys
import logging

from flask import Flask, request, redirect, url_for, render_template, g, session, jsonify, Blueprint

logger = logging.getLogger(__name__)

annotate_bp = Blueprint('annotate', '__name__', url_prefix='/annotate')

def get_db():
	return BlurbStore(os.path.join('.dfx_data', 'BlurbStore.shelve'))

@annotate_bp.route('/')
def index():
	logger.debug('index()')
	db = get_db()
	return render_template('annotate/home.html', previews = db.previews())

@annotate_bp.route('/example')
def example():
	return render_template('annotate/example.html')

@annotate_bp.route('/restart')
def restart():
	"""Delete all blurbs, redirect to home
	"""
	logger.info('restart()')
	session.clear()
	db = get_db()
	db.clear()
	return redirect(url_for('.index'))



@annotate_bp.route('/create', methods=['GET', 'POST'])
def create():
	"""Create a new blurb

	If this ia a GET, return a form. TODO: make a real page.
	If this is a POST, create the new blurb.

	Returns a redirect to the page for the new blurb
	"""
	if request.method == 'GET':
		logger.debug('create() GET')
		return """
			<form action="/annotate/create" method="POST">
				<label for="address">Address:</label>
				<input type="text" name="address" placeholder="address?" />
				<br/>
				<textarea name="content" rows=10 cols=80></textarea>
				<br />
				<input type="submit" />
			</form>	

			"""
	if request.method == 'POST':
		address = str(request.form['address'])
		content = request.form['content']
		logger.debug("create() POST address={}, content={:80s}".format(address, content))
		blurb = Blurb(address, content)
		db = get_db()
		db.put(blurb)
		return redirect(url_for('annotate.view', address=blurb.address))

@annotate_bp.route('/view/<string:address>')
def view(address):
	"""View a blurb

	Returns a HTML page
	"""
	db = get_db()
	address = str(address)
	logger.debug("view() {}".format(address))
	blurb = db.get_with_references(address)
	available_addresses = [_ for _ in db.addresses() if _ != str(address)]
	g.enumerate = enumerate
	g.commands = [{'label': 'home', 'value': url_for('annotate.index')}]
	# if return_to is in the query string, add it as session variable
	if 'return_to' in request.args:
		session['return_to'] = str(request.args['return_to'])
	# if the return_to session matches this blurb, remove it
	if session.get('return_to', None)==str(address):
		del session['return_to']
	return render_template("annotate/blurb.html", blurb=blurb, available_addresses=available_addresses)

@annotate_bp.route('/modify', methods=['POST'])
def modify():
	"""Modified an existing blurb - either the blurb address or content

	Returns JSON with success message. If modifying the address, JSON includes
	the URL of the new page, so that the client-side can change URLs.
	"""
	db = get_db()
	if 'new-address' in request.form:
		old_address = str(request.form['address'])
		new_address = str(request.form['new-address'])
		logger.debug("modify() address old={}, new={}".format(old_address, new_address))
		db.change_address(old_address, new_address)

		# if the session referred to the old address, update it
		if session.get('current_blurb_address', None) == old_address:
			session['current_blurb_address'] = new_address

		return jsonify(dict(
			status="success",
			url=url_for('annotate.view', address = request.form['new-address']),
			))
	if 'new-content' in request.form:
		address = str(request.form['address'])
		content = request.form['new-content']
		logger.debug("modify() content address={}, content={:80s}".format(address, content))
		blurb = db.get(address)
		blurb.content = content
		db.put(blurb)
		return jsonify(dict(status="success"))

@annotate_bp.route('/add-reference', methods=["POST"])
def add_reference():
	"""Add a reference to another blurb

	Returns JSON, including an html render of the referenced blurb so this
	can be inserted into the blurb page

	If the reference address doesn't exist, it creates a new blurb and returns that
	"""
	db = get_db()
	address = str(request.form['address'])
	blurb = db.get(address)
	new_ref_address = str(request.form['new-reference'])
	insert_index = request.form.get('insert-index')
	logger.debug("add_reference(), parent={}, new={}, index={}".format(address, new_ref_address, insert_index))
	create_new = False
	try:
		ref = db.get(new_ref_address)
	except KeyError:
		create_new = True
		#return jsonify({'status': 'fail', 'message': "Could not find reference to " + new_ref_address})

	if create_new:
		ref = Blurb(new_ref_address, "Inserted into {}".format(address))
		db.put(ref)

	if insert_index is None:
		insert_index = len(blurb.ref_list)
	else:
		insert_index = int(insert_index)

	blurb.ref_list.insert(insert_index, new_ref_address)
	db.put(blurb)
	sub_blurb_html = render_template("annotate/sub-blurb.html", blurb=blurb, ref=ref, i=0)
	return jsonify({'status': 'success', 'html': sub_blurb_html})

@annotate_bp.route('/remove-reference', methods=["POST"])
def remove_reference():
	"""Remove a reference to a blurb

	If the blurb didn't include the reference to begin with, no problem, still reports success.

	Returns JSON status message, always 'success'
	"""
	db = get_db()
	address = str(request.form['parent-address'])
	blurb = db.get(address)
	delete_ref_address = str(request.form['ref-address-to-delete'])
	logger.debug("remove_reference(), parent={}, ref={}".format(address, delete_ref_address))
	blurb.ref_list.remove(delete_ref_address)
	db.put(blurb)
	return jsonify({
		'status': 'success', 
		'message': 'Removed reference to <a href="{ref:}">{ref:}</a>'.format(ref=delete_ref_address)
		})

@annotate_bp.route('/move-reference', methods=["POST"])
def move_reference():
	"""Reorder references

	Returns a redirect to the blurb page, since the blurb references
	need to be re-rendered.
	"""
	db = get_db()
	address = str(request.form['parent-address'])
	blurb = db.get(address)
	move_ref_address = str(request.form['ref-address-to-move'])
	current_index = blurb.ref_list.index(move_ref_address)
	destination_index = int(request.form['move-to-index']) - 1
	logger.debug("move_reference() address={}, ref={}, old_index={}, new_index={}".format(address, move_ref_address, current_index, destination_index))
	if current_index != destination_index:
		blurb.ref_list.pop(current_index)
		blurb.ref_list.insert(destination_index, move_ref_address)
		db.put(blurb)
	return redirect(url_for('annotate.view', address=blurb.address))

@annotate_bp.route('/delete', methods=["POST"])
def delete():
	"""Delete a blurb, optionally all sub-blurbs

	Returns redirect to home
	"""
	db = get_db()
	address = str(request.form['address'])
	delete_references = ('delete-references' in request.form)
	logger.debug("delete() address={}, delete_references={}".format(address, delete_references))
	blurb = db.get(address)
	if delete_references:
		for ref in blurb.ref_list:
			db.remove(ref)
	db.remove(address)
	return go_back_or_home()


def go_back_or_home():
	"""Either go back to return_to blurb, or home
	"""
	if 'return_to' in session:
		return redirect(url_for('.view', address=session['return_to']))
	else:
		return redirect(url_for('.index'))


@annotate_bp.route('/add_to_current', methods=['POST'])
def add_to_current():
	"""Add content as a reference from the current blurb

	The current blurb is an address stored in a session variable. If none is
	available, a new blurb is created.

	Returns JSON of the newly created blurb and it's parent
	"""
	db = get_db()

	# get current blurb
	current_blurb_address = session.get('current_blurb_address', None)	
	if current_blurb_address is None or current_blurb_address not in db.addresses():
		address = "main-" + random_address()
		logger.debug("add_to_current() creating current {}".format(address))
		current_blurb = Blurb(address, 'Auto created as current blurb')
		db.put(current_blurb)
		session['current_blurb_address'] = current_blurb.address
	else:
		current_blurb = db.get(current_blurb_address)

	# create new incremental blurb
	blurb = Blurb(random_address(), str(request.form['content']))
	db.put(blurb)
	logger.debug("add_to_current() created new {}".format(blurb.address))

	# add to current
	current_blurb.ref_list.append(blurb.address)
	db.put(current_blurb)

	message = 'Created <a href="/annotate/view/{new:}">{new:}</a> on <a href="/annotate/view/{parent:}">{parent:}</a>'.format(
		new = blurb.address,
		parent = current_blurb.address,
		)
	return jsonify({
		'status': 'success',
		'message': message,
		'new_blurb': blurb.address, 
		'parent_blurb': current_blurb.address
		})




class Blurb(object):
	def __init__(self, address, content): # , ref_list = []
		if type(address) != str:
			raise ValueError('address must be string')
		self.address = address
		self.content = content
		# self.ref_list = ref_list
		self.ref_list = []
	def __str__(self):
		return self.address + ": " + self.content

class BlurbStore(object):
	def __init__(self, path):
		self.path = path
		# make sure we can initialize the object
		shelve.open(self.path, flag='c')

	def put(self, blurb):
		"""Add to database, using the address as key

		Returns nothing
		"""
		s = shelve.open(self.path, flag='c')
		s[blurb.address] = blurb

	def get(self, address):
		"""Get from store based on address

		Returns Blurb

		Throws KeyError for invalid address
		"""
		s = shelve.open(self.path, flag='r')
		return s[address]

	def clear(self):
		"""Delete all items in store
		"""
		s = shelve.open(self.path, flag='c')
		s.clear()
		s.close()

	def remove(self, address, delete_references=True):
		"""Remove blurb from store, and delete all references to it

		Returns nothing
		"""
		s = shelve.open(self.path, flag='c')
		del s[address]
		if delete_references:
			for blurb in s.values():
				need_to_save = False
				while True:
					try:
						i = blurb.ref_list.index(address)
						blurb.ref_list.pop(i)
						need_to_save = True
					except ValueError as e:
						break
				if need_to_save:
					s[blurb.address] = blurb

	def addresses(self):
		"""Return a list of all keys
		"""
		s = shelve.open(self.path, flag='r')
		return s.keys()

	def previews(self):
		"""Return a list of (address, content)
		"""
		s = shelve.open(self.path, flag='r')
		previews = []
		keys = s.keys()
		for key in keys:
			blurb = s[key]
			previews.append((key, blurb.content))
		return previews


	def get_with_references(self, address):
		"""Returns a blurb along with the content of all of it's sub-blurbs

		This adds .ref_list_resolved to the returned Blurb, which is a list
		of Blurbs
		"""
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
		"""Change the address of a blurb, and update all references to it

		Returns nothing
		"""
		blurb = self.get(old_address)
		blurb.address = new_address
		self.put(blurb)
		self.remove(old_address, delete_references=False)

		# iterate over all other blurbs in the store and change references if necessary
		for address in self.addresses():
			other_blurb = self.get(address)
			if old_address in other_blurb.ref_list:
				other_blurb.ref_list = [new_address if other_blurb_ref == old_address else other_blurb_ref for other_blurb_ref in other_blurb.ref_list]
				self.put(other_blurb)

def random_address():
	return 'blurb-' + ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))

