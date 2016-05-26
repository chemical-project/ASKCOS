import numpy as np
import rdkit.Chem.Descriptors as Descriptors
import rdkit.Chem.rdMolDescriptors as rdMolDescriptors
import rdkit.Chem.EState as EState
import rdkit.Chem.rdPartialCharges as rdPartialCharges

att_dtype = np.float32

def mol_level_descriptors(mol):
	'''
	Given an RDKit mol, returns a list of molecule-level descriptors 
	and their names

	returns: (labels, attributes)
	'''
	
	labels = [label for (label, f) in Descriptors._descList]
	attributes = [f(mol) for (label, f) in Descriptors._descList]
	
	return (labels, attributes)

def atom_level_descriptors(mol, include = ['functional'], asOneHot = False):
	'''
	Given an RDKit mol, returns an N_atom-long list of lists,
	each of which contains atom-level descriptors and their names

	returns: (label, attributes)
	'''

	attributes = [[] for i in mol.GetAtoms()]
	labels = []
	if 'functional' in include:

		[attributes[i].append(x[0]) \
			for (i, x) in enumerate(rdMolDescriptors._CalcCrippenContribs(mol))]
		labels.append('Crippen contribution to logp')

		[attributes[i].append(x[1]) \
			for (i, x) in enumerate(rdMolDescriptors._CalcCrippenContribs(mol))]
		labels.append('Crippen contribution to mr')

		[attributes[i].append(x) \
			for (i, x) in enumerate(rdMolDescriptors._CalcTPSAContribs(mol))]
		labels.append('TPSA contribution')

		[attributes[i].append(x) \
			for (i, x) in enumerate(rdMolDescriptors._CalcLabuteASAContribs(mol)[0])]
		labels.append('Labute ASA contribution')

		[attributes[i].append(x) \
			for (i, x) in enumerate(EState.EStateIndices(mol))]
		labels.append('EState Index')

		rdPartialCharges.ComputeGasteigerCharges(mol)
		[attributes[i].append(float(a.GetProp('_GasteigerCharge'))) \
			for (i, a) in enumerate(mol.GetAtoms())]
		labels.append('Gasteiger partial charge')

		[attributes[i].append(float(a.GetProp('_GasteigerHCharge'))) \
			for (i, a) in enumerate(mol.GetAtoms())]
		labels.append('Gasteiger hydrogen partial charge')
	
	if 'structural' in include:
		[attributes[i].extend(atom_structural(mol.GetAtomWithIdx(i), asOneHot = asOneHot)) \
			for i in range(len(attributes))]
		labels.append('--many structural--')

	return (labels, attributes)

def bond_structural(bond, asOneHot = False, extraOne = False):
	'''
	Returns a numpy array of attributes for an RDKit bond
	- Bond type as double
	- If bond is aromatic
	- If bond is conjugated
	- If bond is in ring
	'''

	# Redefine oneHotVector function
	if not asOneHot: oneHotVector = lambda x: x[0]

	# Initialize
	attributes = []
	# Add bond type
	attributes += oneHotVector(
		bond.GetBondTypeAsDouble(),
		[1.0, 1.5, 2.0, 3.0]
	)
	# Add if is aromatic
	attributes.append(bond.GetIsAromatic())
	# Add if bond is conjugated
	attributes.append(bond.GetIsConjugated())
	# Add if bond is part of ring
	attributes.append(bond.IsInRing())

	# NEED THIS FOR TENSOR REPRESENTATION - 1 IF THERE IS A BOND
	if extraOne: attributes.append(1)

	return np.array(attributes, dtype = att_dtype)

def atom_structural(atom, asOneHot = False):
	'''
	Returns a numpy array of attributes for an RDKit atom
	- atomic number
	- number of heavy neighbors
	- total number of hydrogen neighbors
	- formal charge
	- is in a ring
	- is aromatic
    '''

   	# Redefine oneHotVector function
	if not asOneHot: oneHotVector = lambda x: x[0]

	# Initialize
	attributes = []
	# Add atomic number (todo: finish)
	attributes += oneHotVector(
		atom.GetAtomicNum(), 
		[5, 6, 7, 8, 9, 15, 16, 17, 35, 53, 999]
	)
	# Add heavy neighbor count
	attributes += oneHotVector(
		len(atom.GetNeighbors()),
		[0, 1, 2, 3, 4, 5]
	)
	# Add hydrogen count
	attributes += oneHotVector(
		atom.GetTotalNumHs(),
		[0, 1, 2, 3, 4]
	)
	# Add formal charge
	attributes.append(atom.GetFormalCharge())
	# Add boolean if in ring
	attributes.append(atom.IsInRing())
	# Add boolean if aromatic atom
	attributes.append(atom.GetIsAromatic())

	return np.array(attributes, dtype = att_dtype)

def oneHotVector(val, lst):
	'''Converts a value to a one-hot vector based on options in lst'''
	if val not in lst:
		val = lst[-1]
	return map(lambda x: x == val, lst)