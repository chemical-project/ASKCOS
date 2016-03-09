from __future__ import print_function
from makeit.utils.saving import draw_mol
from makeit.main.reaction_clustering import generate_rxn_embeddings_and_save, cluster
import makeit.utils.stats as stats
import theano # for looking at computational graph
import matplotlib.pyplot as plt
import numpy as np
import datetime
import sys
import os


def test_model(model, get_data, fpath, tstamp = 'no_time', batch_size = 128):
	'''This function evaluates model performance using test data. The output is
	more meaningful than just the loss function value.

	inputs:
		model - the trained Keras model
		get_data - a function that returns three dictionaries for training,
					validation, and testing data. Each dictionary should have
					keys of 'mol', a molecular tensor, 'y', the target output, 
					and 'smiles', the SMILES string of that molecule
		fpath - folderpath to save test data to, will be appended with '/tstamp.test'
		tstamp - timestamp to add to the testing
		batch_size - batch_size to use while testing'''
	
	# Create folder to dump testing info to
	try:
		os.makedirs(fpath)
	except: # file exists
		pass
	test_fpath = os.path.join(fpath, tstamp)

	# Get data from helper function
	(train, val, test) = get_data()
	# Unpack
	mols_train = train['mols']; y_train = train['y']; smiles_train = train['smiles']
	mols_val   = val['mols'];   y_val   = val['y'];   smiles_val   = val['smiles']
	mols_test  = test['mols'];  y_test  = test['y'];  smiles_test  = test['smiles']
	y_label = train['y_label']

	# Fit (allows keyboard interrupts in the middle)
	# Because molecular graph tensors are different sizes based on N_atoms, can only do one at a time
	# (alternative is to pad with zeros and try to add some masking feature to GraphFP)
	y_train_pred = []
	y_val_pred = []
	y_test_pred = []

	if batch_size == 1: # UNEVEN TENSORS, ONE AT A TIME PREDICTION
		# Run through training set
		for j in range(len(mols_train)):
			single_mol_as_array = np.array(mols_train[j:j+1])
			single_y_as_array = np.array(y_train[j:j+1])
			spred = float(model.predict_on_batch(single_mol_as_array)[0][0][0])
			y_train_pred.append(spred)

		# Run through validation set
		for j in range(len(mols_val)):
			single_mol_as_array = np.array(mols_val[j:j+1])
			spred = float(model.predict_on_batch(single_mol_as_array)[0][0][0])
			y_val_pred.append(spred)

		# Run through testing set
		for j in range(len(mols_test)):
			single_mol_as_array = np.array(mols_test[j:j+1])
			spred = float(model.predict_on_batch(single_mol_as_array)[0][0][0])
			y_test_pred.append(spred)

	else: # PADDED
		y_train_pred = model.predict(np.array(mols_train), batch_size = batch_size, verbose = 1)[:, 0]
		y_val_pred = model.predict(np.array(mols_val), batch_size = batch_size, verbose = 1)[:, 0]
		y_test_pred = model.predict(np.array(mols_test), batch_size = batch_size, verbose = 1)[:, 0]

	# Save
	with open(test_fpath + '.test', 'w') as fid:
		fid.write('{} tested at UTC {}, predicting {}\n\n'.format(fpath, tstamp, y_label))		
		fid.write('test entry\tsmiles\tactual\tpredicted\tactual - predicted\n')
		for i in range(len(smiles_test)):
			fid.write('{}\t{}\t{}\t{}\t{}\n'.format(i, 
				smiles_test[i],
				y_test[i], 
				y_test_pred[i],
				y_test[i] - y_test_pred[i]))

	def round3(x):
		return int(x * 1000) / 1000.0

	def parity_plot(true, pred, set_label):
		if len(true) == 0:
			print('skipping parity plot for empty dataset')
			return

		# Calculate some stats
		min_y = np.min((true, pred))
		max_y = np.max((true, pred))
		mse = stats.mse(true, pred)
		mae = stats.mae(true, pred)
		q = stats.q(true, pred)
		(r2, a) = stats.linreg(true, pred) # predicted v observed
		(r2p, ap) = stats.linreg(pred, true) # observed v predicted

		# Create parity plot
		plt.scatter(true, pred, alpha = 0.5)
		plt.xlabel('Actual {}'.format(y_label))
		plt.ylabel('Predicted {}'.format(y_label))
		plt.title('Parity plot for {} ({} set, N = {})'.format(y_label, set_label, len(true)) + 
			'\nMSE = {}, MAE = {}, q = {}'.format(round3(mse), round3(mae), round3(q)) + 
			'\na = {}, r^2 = {}'.format(round3(a), round3(r2)) + 
			'\na` = {}, r^2` = {}'.format(round3(ap), round3(r2p)))
		plt.grid(True)
		plt.plot(true, true * a, 'r--')
		plt.axis([min_y, max_y, min_y, max_y])	
		plt.savefig(test_fpath + ' {}.png'.format(label), bbox_inches = 'tight')
		plt.clf()

		# Print
		print('{}:'.format(label))
		print('  mse = {}, mae = {}'.format(mse, mae))
		print('  q = {}'.format(q))
		print('  r2 through origin = {} (pred v. true), {} (true v. pred)'.format(r2, r2p))
		print('  slope through origin = {} (pred v. true), {} (true v. pred)'.format(a[0], ap[0]))

	# Create plots for datasets
	parity_plot(y_train, y_train_pred, 'train')
	parity_plot(y_val, y_val_pred, 'val')
	parity_plot(y_test, y_test_pred, 'test')

	return

def test_reactions(model, fpath):
	'''This function tests how reactions are embedded

	IN PROGRESS'''

	# Create folder to dump testing info to
	try:
		os.makedirs(fpath)
	except: # folder exists
		pass
	try:
		fpath = os.path.join(fpath, 'embeddings')
		os.makedirs(fpath)
	except: # folder exists
		pass

	# Define function to test embedding
	tf = K.function([model.layers[0].input], 
		model.layers[0].get_output(train = False))

	# Embed reactions
	(embebddings, smiles) = generate_rxn_embeddings_and_save(embedding_func, fpath)
	cluster(embeddings, smiles)

def test_embeddings_demo(model, get_data, fpath):
	'''This function tests molecular representations by creating visualizations
	of fingerprints given a SMILES string.

	inputs:
		model - the trained Keras model
		get_data - a function that returns three dictionaries for training,
					validation, and testing data. Each dictionary should have
					keys of 'mol', a molecular tensor, 'y', the target output, 
					and 'smiles', the SMILES string of that molecule
		fpath - folderpath to save test data to, will be appended with '/embeddings/'
		'''
	print('Building images of fingerprint examples')

	# Create folder to dump testing info to
	try:
		os.makedirs(fpath)
	except: # folder exists
		pass
	try:
		fpath = os.path.join(fpath, 'embeddings')
		os.makedirs(fpath)
	except: # folder exists
		pass

	# Get data from helper function
	(train, val, test) = get_data()
	# Unpack
	mols_train = train['mols']; y_train = train['y']; smiles_train = train['smiles']
	mols_val   = val['mols'];   y_val   = val['y'];   smiles_val   = val['smiles']
	mols_test  = test['mols'];  y_test  = test['y'];  smiles_test  = test['smiles']
	y_label = train['y_label']

	# Define function to test embedding
	tf = K.function([model.layers[0].input], 
		model.layers[0].get_output(train = False))

	# Define function to save image
	def embedding_to_png(embedding, label, fpath):
		fig = plt.figure(figsize=(20,0.5))
		plt.pcolor(embedding, vmin = 0, vmax = 1)
		plt.title('{}'.format(label))
		# cbar = plt.colorbar()
		plt.gca().yaxis.set_visible(False)
		plt.gca().xaxis.set_visible(False)
		plt.xlim([0, 512])
		plt.subplots_adjust(left = 0, right = 1, top = 0.4, bottom = 0)
		plt.savefig(os.path.join(fpath, label) + '.png', bbox_inches = 'tight')
		plt.close(fig)
		plt.clf()
		return

	# Run through training set
	for j in range(len(mols_train)):
		continue # placeholder
		single_mol_as_array = np.array(mols_train[j:j+1])
		embedding = tf([single_mol_as_array])
		embedding_to_png(embedding, smiles_train[j], fpath)
		if j == 25:
			break

	# Run through validation set
	for j in range(len(mols_val)):
		continue # placeholder
		single_mol_as_array = np.array(mols_val[j:j+1])

	# Run through testing set
	for j in range(len(mols_test)):
		continue # placeholder
		single_mol_as_array = np.array(mols_test[j:j+1])

	smiles = ''
	while True:
		smiles = raw_input('Enter smiles: ').strip()
		if smiles is 'done':
			break
		try:
			mol = Chem.MolFromSmiles(smiles)
			mol_graph = molToGraph(mol).dump_as_tensor()
			single_mol_as_array = np.array([mol_graph])
			embedding = tf([single_mol_as_array])
			embedding_to_png(embedding, smiles, fpath)
		except:
			print('error saving embedding - was that a SMILES string?')

	return

def test_activations(model, get_data, fpath, contribution_threshold = 0.5):
	'''This function tests activation of the output for a LINEAR model

	inputs:
		model - the trained Keras model
		get_data - a function that returns three dictionaries for training,
					validation, and testing data. Each dictionary should have
					keys of 'mol', a molecular tensor, 'y', the target output, 
					and 'smiles', the SMILES string of that molecule
		fpath - folderpath to save test data to, will be appended with '/embeddings/'
		contribution_threshold - the minimum amount that a certain atom contributes 
					a fingerprint entry to warrant highlighting (and saving)
	'''

	# Create folder to dump testing info to
	try:
		os.makedirs(fpath)
	except: # folder exists
		pass
	try:
		fpath = os.path.join(fpath, 'embeddings')
		os.makedirs(fpath)
	except: # folder exists
		pass

	# Get data from helper function
	(train, val, test) = get_data()
	# Unpack
	mols_train = train['mols']; y_train = train['y']; smiles_train = train['smiles']
	mols_val   = val['mols'];   y_val   = val['y'];   smiles_val   = val['smiles']
	mols_test  = test['mols'];  y_test  = test['y'];  smiles_test  = test['smiles']
	y_label = train['y_label']

	# Loop through fingerprint indeces in dense layer
	dense_weights = model.layers[1].get_weights()[0] # weights, not bias
	# Save histogram
	weights = np.ones_like(dense_weights) / len(dense_weights)
	n, bins, patches = plt.hist(dense_weights, 50, facecolor = 'blue', alpha = 0.5, weights = weights)
	plt.xlabel('FP index contribution to predicted {}'.format(y_label))
	plt.ylabel('Normalized frequency')
	plt.title('Histogram of weights for linear [FP->{}] model'.format(y_label))
	plt.grid(True)
	plt.savefig(fpath + '/weights_histogram.png', bbox_inches = 'tight')

	# Now report 5 most positive activations:
	sorted_indeces = sorted(range(len(dense_weights)), key = lambda i: dense_weights[i])
	most_neg = []
	print('Most negatively-activating fingerprint indeces:')
	for j in range(3):
		print('at index {}, weight = {}'.format(sorted_indeces[j], dense_weights[sorted_indeces[j]]))
		most_neg.append(sorted_indeces[j])
	most_pos = []
	print('Most negatively-activating fingerprint indeces:')
	for j in range(1, 4):
		print('at index {}, weight = {}'.format(sorted_indeces[-j], dense_weights[sorted_indeces[-j]]))
		most_pos.append(sorted_indeces[-j])

	# Define function to test embedding
	tf = K.function([model.layers[0].input], 
		model.layers[0].get_output_singlesample_detail(train = False))

	# Look at most activating for each?
	for fp_ind in most_neg + most_pos:
		print('Looking at index {}'.format(fp_ind))
		for j in range(len(mols_train)):
			# print('Looking at training molecule {}'.format(j))
			single_mol_as_array = np.array(mols_train[j:j+1])
			embedding = tf([single_mol_as_array])
			if j in range(5):
				print(embedding)
			for depth in range(embedding.shape[2]):
				highlight_atoms = []
				for atom in range(embedding.shape[0]):
					if embedding[atom, fp_ind, depth] > contribution_threshold:
						# print('Atom {} at depth {} triggers fp_index {}'.format(atom, depth, fp_ind))
						if atom not in highlight_atoms:
							highlight_atoms.append(atom)
			if highlight_atoms: # is not empty
				mol = Chem.MolFromSmiles(smiles_train[j])
				draw_mol(mol, fpath + '/index{}_'.format(fp_ind) + smiles_train[j] + '.png'.format(depth), highlightAtoms = highlight_atoms)
			else:
				# No activations
				pass

	return