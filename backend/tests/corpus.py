"""Name corpus for exhaustive parsing/stereo/3D tests.

Each entry: (name, expected_centers, expected_double_bonds, category)
  expected_centers      number of R/S-labelled tetrahedral centres, or None to skip the count
  expected_double_bonds number of E/Z-labelled double bonds, or None to skip the count
All entries must resolve, must not have unspecified stereo, and the 3D
geometry must reproduce every labelled element.
"""

CORPUS: list[tuple[str, int | None, int | None, str]] = [
    # --- alkanes / branched / cycloalkanes ---
    ("methane", 0, 0, "alkane"),
    ("2,2,4-trimethylpentane", 0, 0, "alkane"),
    ("(3R)-3-methylhexane", 1, 0, "alkane"),
    ("(3S)-3-methylhexane", 1, 0, "alkane"),
    ("(4R)-4-ethyl-2-methylheptane", 1, 0, "alkane"),
    ("cyclopropane", 0, 0, "cycloalkane"),
    ("cyclohexane", 0, 0, "cycloalkane"),
    ("methylcyclohexane", 0, 0, "cycloalkane"),
    ("cis-1,2-dimethylcyclohexane", 2, 0, "cycloalkane"),
    ("trans-1,2-dimethylcyclohexane", 2, 0, "cycloalkane"),
    ("(1R,2R)-1,2-dimethylcyclohexane", 2, 0, "cycloalkane"),
    ("(1S,2S)-1,2-dimethylcyclopentane", 2, 0, "cycloalkane"),
    ("cis-1,3-dimethylcyclohexane", 2, 0, "cycloalkane"),
    ("trans-1,4-dimethylcyclohexane", 2, 0, "cycloalkane"),  # pseudo-asymmetric r/r
    ("cis-1,4-dimethylcyclohexane", 2, 0, "cycloalkane"),  # s/s
    ("(1R,2S)-1-ethyl-2-methylcyclohexane", 2, 0, "cycloalkane"),
    ("cyclododecane", 0, 0, "cycloalkane"),
    # --- alkenes / E-Z ---
    ("ethene", 0, 0, "alkene"),
    ("propene", 0, 0, "alkene"),
    ("but-1-ene", 0, 0, "alkene"),
    ("(2E)-but-2-ene", 0, 1, "alkene"),
    ("(2Z)-but-2-ene", 0, 1, "alkene"),
    ("(E)-pent-2-ene", 0, 1, "alkene"),
    ("(Z)-hex-3-ene", 0, 1, "alkene"),
    ("(2E,4E)-hexa-2,4-diene", 0, 2, "alkene"),
    ("(2E,4Z)-hexa-2,4-diene", 0, 2, "alkene"),
    ("(2Z,4Z)-hexa-2,4-diene", 0, 2, "alkene"),
    ("2-methylbut-2-ene", 0, 0, "alkene"),
    ("(E)-3-methylpent-2-ene", 0, 1, "alkene"),
    ("(Z)-1-chloroprop-1-ene", 0, 1, "alkene"),
    ("(E)-1,2-dichloroethene", 0, 1, "alkene"),
    ("(Z)-1,2-dichloroethene", 0, 1, "alkene"),
    ("(E)-stilbene", 0, 1, "alkene"),
    ("(Z)-1,2-diphenylethene", 0, 1, "alkene"),
    ("buta-1,3-diene", 0, 0, "alkene"),
    ("(3E)-penta-1,3-diene", 0, 1, "alkene"),
    ("cyclohexene", 0, 0, "alkene"),
    ("(E)-cyclooctene", 0, 1, "alkene"),
    ("(Z)-cyclooctene", 0, 1, "alkene"),
    ("(2E,4E,6E)-octa-2,4,6-triene", 0, 3, "alkene"),
    ("(3E)-4-methylhex-3-ene", 0, 1, "alkene"),
    ("(2E)-2-butenal", 0, 1, "alkene"),
    ("(E)-but-2-enoic acid", 0, 1, "alkene"),
    ("(Z)-but-2-enedioic acid", 0, 1, "alkene"),
    ("(E)-but-2-enedioic acid", 0, 1, "alkene"),
    ("(3R)-3-methylpent-1-ene", 1, 0, "alkene"),
    ("(3S,4E)-3-methylhex-4-ene", 1, 1, "alkene"),
    ("(2E,4R)-4-methylhex-2-ene", 1, 1, "alkene"),
    ("(5Z,8Z,11Z,14Z)-icosa-5,8,11,14-tetraenoic acid", 0, 4, "alkene"),
    ("(9Z,12Z)-octadeca-9,12-dienoic acid", 0, 2, "alkene"),
    ("(9E)-octadec-9-enoic acid", 0, 1, "alkene"),
    ("(9Z)-octadec-9-enoic acid", 0, 1, "alkene"),
    # --- alkynes ---
    ("ethyne", 0, 0, "alkyne"),
    ("propyne", 0, 0, "alkyne"),
    ("but-2-yne", 0, 0, "alkyne"),
    ("hex-1-en-5-yne", 0, 0, "alkyne"),
    ("(3R)-3-methylpent-1-yne", 1, 0, "alkyne"),
    ("(E)-hex-2-en-4-yne", 0, 1, "alkyne"),
    ("phenylethyne", 0, 0, "alkyne"),
    ("diphenylethyne", 0, 0, "alkyne"),
    # --- aromatics ---
    ("benzene", 0, 0, "aromatic"),
    ("toluene", 0, 0, "aromatic"),
    ("1,2-dimethylbenzene", 0, 0, "aromatic"),
    ("1,3,5-trimethylbenzene", 0, 0, "aromatic"),
    ("naphthalene", 0, 0, "aromatic"),
    ("anthracene", 0, 0, "aromatic"),
    ("phenanthrene", 0, 0, "aromatic"),
    ("pyrene", 0, 0, "aromatic"),
    ("biphenyl", 0, 0, "aromatic"),
    ("4-nitrotoluene", 0, 0, "aromatic"),
    ("1,3-dinitrobenzene", 0, 0, "aromatic"),
    ("2,4,6-trinitrotoluene", 0, 0, "aromatic"),
    ("phenol", 0, 0, "aromatic"),
    ("4-methylphenol", 0, 0, "aromatic"),
    ("benzene-1,2-diol", 0, 0, "aromatic"),
    ("aniline", 0, 0, "aromatic"),
    ("N,N-dimethylaniline", 0, 0, "aromatic"),
    ("benzoic acid", 0, 0, "aromatic"),
    ("2-hydroxybenzoic acid", 0, 0, "aromatic"),
    ("benzaldehyde", 0, 0, "aromatic"),
    ("acetophenone", 0, 0, "aromatic"),
    ("benzophenone", 0, 0, "aromatic"),
    ("styrene", 0, 0, "aromatic"),
    ("chlorobenzene", 0, 0, "aromatic"),
    ("1-bromo-4-chlorobenzene", 0, 0, "aromatic"),
    ("hexafluorobenzene", 0, 0, "aromatic"),
    ("(1R)-1-phenylethanol", 1, 0, "aromatic"),
    ("(1S)-1-phenylethan-1-amine", 1, 0, "aromatic"),
    ("(2R)-2-phenylpropanoic acid", 1, 0, "aromatic"),
    # --- halides ---
    ("chloromethane", 0, 0, "halide"),
    ("dichloromethane", 0, 0, "halide"),
    ("trichloromethane", 0, 0, "halide"),
    ("tetrachloromethane", 0, 0, "halide"),
    ("bromoethane", 0, 0, "halide"),
    ("2-iodopropane", 0, 0, "halide"),
    ("1,1,1-trifluoroethane", 0, 0, "halide"),
    ("(2R)-2-chlorobutane", 1, 0, "halide"),
    ("(2S)-2-bromobutane", 1, 0, "halide"),
    ("(2R,3R)-2,3-dibromobutane", 2, 0, "halide"),
    ("(2S,3S)-2,3-dibromobutane", 2, 0, "halide"),
    ("(2R,3S)-2,3-dibromobutane", 2, 0, "halide"),
    ("(1R,2S)-1,2-dibromo-1,2-diphenylethane", 2, 0, "halide"),
    ("(R)-bromochlorofluoromethane", 1, 0, "halide"),
    ("(S)-bromochlorofluoromethane", 1, 0, "halide"),
    ("(2R)-1,2-dibromopropane", 1, 0, "halide"),
    ("1-chloro-2,2-dimethylpropane", 0, 0, "halide"),
    ("(1R,2R)-1,2-dichlorocyclohexane", 2, 0, "halide"),
    ("trans-1,2-dichlorocyclopentane", 2, 0, "halide"),
    # --- alcohols / ethers / phenols ---
    ("methanol", 0, 0, "alcohol"),
    ("ethanol", 0, 0, "alcohol"),
    ("propan-2-ol", 0, 0, "alcohol"),
    ("2-methylpropan-2-ol", 0, 0, "alcohol"),
    ("(2R)-butan-2-ol", 1, 0, "alcohol"),
    ("(2S)-butan-2-ol", 1, 0, "alcohol"),
    ("(2R)-pentan-2-ol", 1, 0, "alcohol"),
    ("(2R,3R)-butane-2,3-diol", 2, 0, "alcohol"),
    ("(2R,3S)-butane-2,3-diol", 2, 0, "alcohol"),
    ("ethane-1,2-diol", 0, 0, "alcohol"),
    ("propane-1,2,3-triol", 0, 0, "alcohol"),
    ("(2R)-propane-1,2-diol", 1, 0, "alcohol"),
    ("cyclohexanol", 0, 0, "alcohol"),
    ("(1R,2S)-2-methylcyclohexan-1-ol", 2, 0, "alcohol"),
    ("(1R,2R)-2-methylcyclohexan-1-ol", 2, 0, "alcohol"),
    ("(1R,2S,5R)-2-isopropyl-5-methylcyclohexanol", 3, 0, "alcohol"),  # (-)-menthol
    ("(1S,2R,5S)-5-methyl-2-(propan-2-yl)cyclohexan-1-ol", 3, 0, "alcohol"),  # (+)-menthol
    ("prop-2-en-1-ol", 0, 0, "alcohol"),
    ("(2E)-but-2-en-1-ol", 0, 1, "alcohol"),
    ("dimethyl ether", 0, 0, "ether"),
    ("methoxymethane", 0, 0, "ether"),
    ("ethoxyethane", 0, 0, "ether"),
    ("oxolane", 0, 0, "ether"),
    ("1,4-dioxane", 0, 0, "ether"),
    ("methoxybenzene", 0, 0, "ether"),
    ("(2R)-2-methyloxirane", 1, 0, "ether"),
    ("(2S)-2-methyloxirane", 1, 0, "ether"),
    ("(2R,3R)-2,3-dimethyloxirane", 2, 0, "ether"),
    ("(2R,3S)-2,3-dimethyloxirane", 2, 0, "ether"),
    ("(2R)-2-methyloxolane", 1, 0, "ether"),
    ("(2S)-oxolan-2-ylmethanol", 1, 0, "ether"),
    # --- aldehydes / ketones ---
    ("methanal", 0, 0, "carbonyl"),
    ("ethanal", 0, 0, "carbonyl"),
    ("propanal", 0, 0, "carbonyl"),
    ("propanone", 0, 0, "carbonyl"),
    ("butan-2-one", 0, 0, "carbonyl"),
    ("pentane-2,4-dione", 0, 0, "carbonyl"),
    ("cyclohexanone", 0, 0, "carbonyl"),
    ("cyclohex-2-en-1-one", 0, 0, "carbonyl"),
    ("(2R)-2-methylbutanal", 1, 0, "carbonyl"),
    ("(2S)-2-methylbutanal", 1, 0, "carbonyl"),
    ("(3R)-3-methylpentan-2-one", 1, 0, "carbonyl"),
    ("(2S)-2-methylcyclohexan-1-one", 1, 0, "carbonyl"),
    ("(3R)-3-methylcyclohexan-1-one", 1, 0, "carbonyl"),
    ("(1R,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one", 2, 0, "carbonyl"),  # (+)-camphor
    ("(1S,4S)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one", 2, 0, "carbonyl"),  # (-)-camphor
    ("(2R,3R)-2,3-dihydroxybutanedial", 2, 0, "carbonyl"),
    ("(E)-4-phenylbut-3-en-2-one", 0, 1, "carbonyl"),
    # --- carboxylic acids and derivatives ---
    ("methanoic acid", 0, 0, "acid"),
    ("ethanoic acid", 0, 0, "acid"),
    ("acetic acid", 0, 0, "acid"),
    ("propanoic acid", 0, 0, "acid"),
    ("butanoic acid", 0, 0, "acid"),
    ("hexadecanoic acid", 0, 0, "acid"),
    ("octadecanoic acid", 0, 0, "acid"),
    ("ethanedioic acid", 0, 0, "acid"),
    ("butanedioic acid", 0, 0, "acid"),
    ("hexanedioic acid", 0, 0, "acid"),
    ("(2S)-2-hydroxypropanoic acid", 1, 0, "acid"),  # L-lactic
    ("(2R)-2-hydroxypropanoic acid", 1, 0, "acid"),  # D-lactic
    ("(2R,3R)-2,3-dihydroxybutanedioic acid", 2, 0, "acid"),  # L-tartaric
    ("(2S,3S)-2,3-dihydroxybutanedioic acid", 2, 0, "acid"),
    ("(2R,3S)-2,3-dihydroxybutanedioic acid", 2, 0, "acid"),  # meso
    ("(2S)-2-hydroxybutanedioic acid", 1, 0, "acid"),  # L-malic
    ("2-hydroxypropane-1,2,3-tricarboxylic acid", 0, 0, "acid"),  # citric
    ("(2R)-2-[4-(2-methylpropyl)phenyl]propanoic acid", 1, 0, "acid"),  # ibuprofen
    ("(2S)-2-[4-(2-methylpropyl)phenyl]propanoic acid", 1, 0, "acid"),
    ("(2S)-2-(6-methoxynaphthalen-2-yl)propanoic acid", 1, 0, "acid"),  # naproxen
    ("(2E,4Z)-hexa-2,4-dienoic acid", 0, 2, "acid"),
    ("(2E,4E)-hexa-2,4-dienoic acid", 0, 2, "acid"),
    ("2-acetyloxybenzoic acid", 0, 0, "acid"),  # aspirin
    ("methyl ethanoate", 0, 0, "ester"),
    ("ethyl acetate", 0, 0, "ester"),
    ("ethyl butanoate", 0, 0, "ester"),
    ("methyl benzoate", 0, 0, "ester"),
    ("methyl (2R)-2-hydroxypropanoate", 1, 0, "ester"),
    ("(2S)-butan-2-yl acetate", 1, 0, "ester"),
    ("methyl (E)-but-2-enoate", 0, 1, "ester"),
    ("diethyl (2R,3R)-2,3-dihydroxybutanedioate", 2, 0, "ester"),
    ("ethanoyl chloride", 0, 0, "acyl halide"),
    ("benzoyl chloride", 0, 0, "acyl halide"),
    ("ethanoic anhydride", 0, 0, "anhydride"),
    ("ethanamide", 0, 0, "amide"),
    ("N-methylethanamide", 0, 0, "amide"),
    ("N,N-dimethylmethanamide", 0, 0, "amide"),
    ("benzamide", 0, 0, "amide"),
    ("N-phenylethanamide", 0, 0, "amide"),
    ("(2S)-2-aminopropanamide", 1, 0, "amide"),
    ("N-(4-hydroxyphenyl)acetamide", 0, 0, "amide"),  # paracetamol
    ("urea", 0, 0, "amide"),
    ("pyrrolidin-2-one", 0, 0, "lactam"),
    ("azepan-2-one", 0, 0, "lactam"),
    ("oxolan-2-one", 0, 0, "lactone"),
    ("(5R)-5-methyloxolan-2-one", 1, 0, "lactone"),
    ("(5S)-5-methyloxolan-2-one", 1, 0, "lactone"),
    # --- amines / nitriles / nitro / imines ---
    ("methanamine", 0, 0, "amine"),
    ("N-methylmethanamine", 0, 0, "amine"),
    ("N,N-dimethylmethanamine", 0, 0, "amine"),
    ("ethane-1,2-diamine", 0, 0, "amine"),
    ("cyclohexanamine", 0, 0, "amine"),
    ("(2R)-butan-2-amine", 1, 0, "amine"),
    ("(2S)-butan-2-amine", 1, 0, "amine"),
    ("(1R,2R)-cyclohexane-1,2-diamine", 2, 0, "amine"),
    ("(1S,2S)-cyclohexane-1,2-diamine", 2, 0, "amine"),
    ("(2S)-2-methylpiperidine", 1, 0, "amine"),
    ("(2R)-2-methylpyrrolidine", 1, 0, "amine"),
    ("(2S)-1-methyl-2-(pyridin-3-yl)pyrrolidine", 1, 0, "amine"),  # (S)-nicotine
    ("(R)-1-phenylpropan-2-amine", 1, 0, "amine"),
    ("(S)-1-phenylpropan-2-amine", 1, 0, "amine"),
    ("ethanenitrile", 0, 0, "nitrile"),
    ("benzonitrile", 0, 0, "nitrile"),
    ("prop-2-enenitrile", 0, 0, "nitrile"),
    ("(2R)-2-hydroxypropanenitrile", 1, 0, "nitrile"),
    ("nitromethane", 0, 0, "nitro"),
    ("nitrobenzene", 0, 0, "nitro"),
    ("(2R)-2-nitrobutane", 1, 0, "nitro"),
    ("N-methylidenemethanamine", 0, 0, "imine"),
    ("isocyanatomethane", 0, 0, "isocyanate"),
    ("azidomethane", 0, 0, "azide"),
    # --- sulfur / phosphorus / silicon / boron ---
    ("methanethiol", 0, 0, "sulfur"),
    ("ethanethiol", 0, 0, "sulfur"),
    ("dimethyl sulfide", 0, 0, "sulfur"),
    ("dimethyl sulfoxide", 0, 0, "sulfur"),
    ("dimethyl sulfone", 0, 0, "sulfur"),
    ("thiophene", 0, 0, "sulfur"),
    ("benzenesulfonic acid", 0, 0, "sulfur"),
    ("4-methylbenzenesulfonyl chloride", 0, 0, "sulfur"),
    ("methanesulfonic acid", 0, 0, "sulfur"),
    ("thiourea", 0, 0, "sulfur"),
    ("(2R)-butane-2-thiol", 1, 0, "sulfur"),
    ("(2R)-2-(methylsulfanyl)butane", 1, 0, "sulfur"),
    ("(R)-methyl phenyl sulfoxide", 1, 0, "sulfur"),  # S-stereocentre
    ("(S)-methyl phenyl sulfoxide", 1, 0, "sulfur"),
    ("trimethylphosphane", 0, 0, "phosphorus"),
    ("triphenylphosphane", 0, 0, "phosphorus"),
    ("trimethyl phosphate", 0, 0, "phosphorus"),
    ("phosphoric acid", 0, 0, "phosphorus"),
    ("dimethyl methylphosphonate", 0, 0, "phosphorus"),
    ("tetramethylsilane", 0, 0, "silicon"),
    ("trimethylsilanol", 0, 0, "silicon"),
    ("chlorotrimethylsilane", 0, 0, "silicon"),
    ("phenylboronic acid", 0, 0, "boron"),
    ("trimethylborane", 0, 0, "boron"),
    # --- heterocycles ---
    ("pyridine", 0, 0, "heterocycle"),
    ("pyrimidine", 0, 0, "heterocycle"),
    ("pyrazine", 0, 0, "heterocycle"),
    ("pyridazine", 0, 0, "heterocycle"),
    ("pyrrole", 0, 0, "heterocycle"),
    ("furan", 0, 0, "heterocycle"),
    ("imidazole", 0, 0, "heterocycle"),
    ("pyrazole", 0, 0, "heterocycle"),
    ("oxazole", 0, 0, "heterocycle"),
    ("thiazole", 0, 0, "heterocycle"),
    ("1,2,4-triazole", 0, 0, "heterocycle"),
    ("tetrazole", 0, 0, "heterocycle"),
    ("indole", 0, 0, "heterocycle"),
    ("quinoline", 0, 0, "heterocycle"),
    ("isoquinoline", 0, 0, "heterocycle"),
    ("purine", 0, 0, "heterocycle"),
    ("benzimidazole", 0, 0, "heterocycle"),
    ("benzofuran", 0, 0, "heterocycle"),
    ("benzothiophene", 0, 0, "heterocycle"),
    ("carbazole", 0, 0, "heterocycle"),
    ("acridine", 0, 0, "heterocycle"),
    ("piperidine", 0, 0, "heterocycle"),
    ("piperazine", 0, 0, "heterocycle"),
    ("morpholine", 0, 0, "heterocycle"),
    ("pyrrolidine", 0, 0, "heterocycle"),
    ("azetidine", 0, 0, "heterocycle"),
    ("aziridine", 0, 0, "heterocycle"),
    ("oxetane", 0, 0, "heterocycle"),
    ("thiolane", 0, 0, "heterocycle"),
    ("1,3-dioxolane", 0, 0, "heterocycle"),
    ("2-methylpyridine", 0, 0, "heterocycle"),
    ("pyridin-3-ol", 0, 0, "heterocycle"),
    ("1H-pyrrole-2-carboxylic acid", 0, 0, "heterocycle"),
    ("2-aminopyrimidine", 0, 0, "heterocycle"),
    ("1,3,5-triazine", 0, 0, "heterocycle"),
    ("caffeine", 0, 0, "heterocycle"),
    ("1,3,7-trimethylpurine-2,6-dione", 0, 0, "heterocycle"),
    ("(2R)-2-methylmorpholine", 1, 0, "heterocycle"),
    ("(3S)-piperidin-3-ol", 1, 0, "heterocycle"),
    ("(2S,3R)-3-methylpiperidin-2-yl)methanol", None, None, "heterocycle-skip"),  # malformed on purpose, handled below
    # --- polycyclic / bridged / spiro / fused ---
    ("bicyclo[2.2.1]heptane", 0, 0, "bridged"),
    ("bicyclo[2.2.2]octane", 0, 0, "bridged"),
    ("bicyclo[1.1.1]pentane", 0, 0, "bridged"),
    ("bicyclo[3.3.1]nonane", 0, 0, "bridged"),
    ("adamantane", 0, 0, "bridged"),
    ("tricyclo[3.3.1.1~3,7~]decane", 0, 0, "bridged"),
    ("cubane", 0, 0, "cage"),
    ("bicyclo[2.2.1]hept-2-ene", 0, 0, "bridged"),
    ("(1R,4S)-bicyclo[2.2.1]hept-2-ene", None, 0, "bridged"),  # enantiotopic; label count may be 0 or 2
    ("(1S,2S,4S)-2-methylbicyclo[2.2.1]heptane", 3, 0, "bridged"),
    ("(1R,2S,4S)-bicyclo[2.2.1]heptan-2-ol", 3, 0, "bridged"),
    ("(1R,2R,4S)-bicyclo[2.2.1]heptan-2-ol", 3, 0, "bridged"),
    ("(1R,4S)-bicyclo[2.2.1]heptan-2-one", 2, 0, "bridged"),
    ("(1S,4R)-bicyclo[2.2.1]heptan-2-one", 2, 0, "bridged"),
    ("spiro[4.5]decane", 0, 0, "spiro"),
    ("spiro[2.2]pentane", 0, 0, "spiro"),
    ("spiro[5.5]undecane", 0, 0, "spiro"),
    ("1,4-dioxaspiro[4.5]decane", 0, 0, "spiro"),
    ("cis-decahydronaphthalene", 2, 0, "fused"),
    ("trans-decahydronaphthalene", 2, 0, "fused"),
    ("1,2,3,4-tetrahydronaphthalene", 0, 0, "fused"),
    ("9H-fluorene", 0, 0, "fused"),
    ("indane", 0, 0, "fused"),
    ("(1R)-2,3-dihydro-1H-inden-1-ol", 1, 0, "fused"),
    ("(1S)-2,3-dihydro-1H-inden-1-amine", 1, 0, "fused"),
    ("(1R,2S)-1-amino-2,3-dihydro-1H-inden-2-ol", 2, 0, "fused"),
    ("cyclobutane-1,1-dicarboxylic acid", 0, 0, "ring"),
    ("(1R,2R)-cyclopropane-1,2-dicarboxylic acid", 2, 0, "ring"),
    ("(1R,2S)-cyclopropane-1,2-dicarboxylic acid", 2, 0, "ring"),
    ("cis-cyclobutane-1,3-diol", 2, 0, "ring"),
    # --- amino acids (L series) ---
    ("glycine", 0, 0, "amino acid"),
    ("aminoacetic acid", 0, 0, "amino acid"),
    ("(2S)-2-aminopropanoic acid", 1, 0, "amino acid"),  # Ala
    ("(2R)-2-aminopropanoic acid", 1, 0, "amino acid"),  # D-Ala
    ("L-alanine", 1, 0, "amino acid"),
    ("D-alanine", 1, 0, "amino acid"),
    ("(2S)-2-amino-3-methylbutanoic acid", 1, 0, "amino acid"),  # Val
    ("L-valine", 1, 0, "amino acid"),
    ("(2S)-2-amino-4-methylpentanoic acid", 1, 0, "amino acid"),  # Leu
    ("L-leucine", 1, 0, "amino acid"),
    ("(2S,3S)-2-amino-3-methylpentanoic acid", 2, 0, "amino acid"),  # Ile
    ("L-isoleucine", 2, 0, "amino acid"),
    ("(2S)-2-amino-3-phenylpropanoic acid", 1, 0, "amino acid"),  # Phe
    ("L-phenylalanine", 1, 0, "amino acid"),
    ("(2S)-2-amino-3-(4-hydroxyphenyl)propanoic acid", 1, 0, "amino acid"),  # Tyr
    ("L-tyrosine", 1, 0, "amino acid"),
    ("(2S)-2-amino-3-(1H-indol-3-yl)propanoic acid", 1, 0, "amino acid"),  # Trp
    ("L-tryptophan", 1, 0, "amino acid"),
    ("(2S)-2-amino-3-hydroxypropanoic acid", 1, 0, "amino acid"),  # Ser
    ("L-serine", 1, 0, "amino acid"),
    ("(2S,3R)-2-amino-3-hydroxybutanoic acid", 2, 0, "amino acid"),  # Thr
    ("L-threonine", 2, 0, "amino acid"),
    ("L-allothreonine", 2, 0, "amino acid"),
    ("(2R)-2-amino-3-sulfanylpropanoic acid", 1, 0, "amino acid"),  # Cys (R!)
    ("L-cysteine", 1, 0, "amino acid"),
    ("(2S)-2-amino-4-(methylsulfanyl)butanoic acid", 1, 0, "amino acid"),  # Met
    ("L-methionine", 1, 0, "amino acid"),
    ("(2S)-2-aminobutanedioic acid", 1, 0, "amino acid"),  # Asp
    ("L-aspartic acid", 1, 0, "amino acid"),
    ("(2S)-2-aminopentanedioic acid", 1, 0, "amino acid"),  # Glu
    ("L-glutamic acid", 1, 0, "amino acid"),
    ("(2S)-2,4-diamino-4-oxobutanoic acid", 1, 0, "amino acid"),  # Asn
    ("L-asparagine", 1, 0, "amino acid"),
    ("(2S)-2,5-diamino-5-oxopentanoic acid", 1, 0, "amino acid"),  # Gln
    ("L-glutamine", 1, 0, "amino acid"),
    ("(2S)-2,6-diaminohexanoic acid", 1, 0, "amino acid"),  # Lys
    ("L-lysine", 1, 0, "amino acid"),
    ("(2S)-2-amino-5-(diaminomethylideneamino)pentanoic acid", 1, 0, "amino acid"),  # Arg
    ("L-arginine", 1, 0, "amino acid"),
    ("(2S)-2-amino-3-(1H-imidazol-4-yl)propanoic acid", 1, 0, "amino acid"),  # His
    ("L-histidine", 1, 0, "amino acid"),
    ("(2S)-pyrrolidine-2-carboxylic acid", 1, 0, "amino acid"),  # Pro
    ("L-proline", 1, 0, "amino acid"),
    ("(2S,4R)-4-hydroxypyrrolidine-2-carboxylic acid", 2, 0, "amino acid"),  # Hyp
    ("L-DOPA", 1, 0, "amino acid"),
    ("(2S)-2-amino-3-(3,4-dihydroxyphenyl)propanoic acid", 1, 0, "amino acid"),
    ("(2S)-2-amino-3-selanylpropanoic acid", 1, 0, "amino acid"),  # Sec
    ("4-aminobutanoic acid", 0, 0, "amino acid"),  # GABA
    ("2-aminoethanesulfonic acid", 0, 0, "amino acid"),  # taurine
    # --- peptides ---
    ("glycylglycine", 0, 0, "peptide"),
    ("L-alanyl-L-alanine", 2, 0, "peptide"),
    ("(2S)-2-[[(2S)-2-aminopropanoyl]amino]propanoic acid", 2, 0, "peptide"),
    ("L-alanyl-L-phenylalanine", 2, 0, "peptide"),
    ("L-aspartyl-L-phenylalanine methyl ester", 2, 0, "peptide"),  # aspartame
    ("methyl (2S)-2-[[(2S)-2-amino-3-carboxypropanoyl]amino]-3-phenylpropanoate", 2, 0, "peptide"),
    ("glycyl-L-alanyl-L-serine", 2, 0, "peptide"),
    # --- carbohydrates (open chain) ---
    ("(2R)-2,3-dihydroxypropanal", 1, 0, "sugar"),  # D-glyceraldehyde
    ("(2S)-2,3-dihydroxypropanal", 1, 0, "sugar"),
    ("D-glyceraldehyde", 1, 0, "sugar"),
    ("(2R,3R)-2,3,4-trihydroxybutanal", 2, 0, "sugar"),  # D-erythrose
    ("(2S,3R)-2,3,4-trihydroxybutanal", 2, 0, "sugar"),  # D-threose
    ("(2R,3S,4R)-2,3,4,5-tetrahydroxypentanal", 3, 0, "sugar"),  # D-ribose
    ("(2R,3R,4S,5R)-2,3,4,5,6-pentahydroxyhexanal", 4, 0, "sugar"),  # D-glucose
    ("(2S,3R,4S,5R)-2,3,4,5,6-pentahydroxyhexanal", 4, 0, "sugar"),  # D-mannose
    ("(2R,3S,4S,5R)-2,3,4,5,6-pentahydroxyhexanal", 4, 0, "sugar"),  # D-galactose
    ("(3S,4R,5R)-1,3,4,5,6-pentahydroxyhexan-2-one", 3, 0, "sugar"),  # D-fructose
    ("(2R,3R,4R,5R)-hexane-1,2,3,4,5,6-hexol", 4, 0, "sugar"),  # D-mannitol
    ("(2R,3R,4S,5S)-hexane-1,2,3,4,5,6-hexol", 4, 0, "sugar"),  # D-glucitol? (sorbitol is 2S,3R,4R,5R)
    ("(2S,3R,4R,5R)-hexane-1,2,3,4,5,6-hexol", 4, 0, "sugar"),  # D-sorbitol
    ("(2R,3S,4R,5R)-2,3,4,5,6-pentahydroxyhexanoic acid", 4, 0, "sugar"),  # D-gluconic acid
    ("(2R,3S,4R,5S)-2,3,4,5,6-pentahydroxyhexanoic acid", 4, 0, "sugar"),
    ("D-glucose", 4, 0, "sugar"),
    ("D-fructose", 3, 0, "sugar"),
    ("L-arabinose", 3, 0, "sugar"),
    ("D-xylose", 3, 0, "sugar"),
    ("L-ascorbic acid", 2, 0, "sugar"),
    ("(5R)-5-[(1S)-1,2-dihydroxyethyl]-3,4-dihydroxyfuran-2(5H)-one", 2, 0, "sugar"),  # vitamin C
    # --- cyclic sugars (pyranoses) ---
    ("(2R,3R,4S,5S,6R)-6-(hydroxymethyl)oxane-2,3,4,5-tetrol", 5, 0, "sugar ring"),  # alpha-D-glucopyranose
    ("(2R,3S,4S,5R,6S)-6-(hydroxymethyl)oxane-2,3,4,5-tetrol", None, 0, "sugar ring"),
    ("(2S,3R,4S,5S,6R)-6-(hydroxymethyl)oxane-2,3,4,5-tetrol", 5, 0, "sugar ring"),  # beta-D-glucopyranose
    ("(2R,3S,4R,5R)-oxane-2,3,4,5-tetrol", 4, 0, "sugar ring"),
    ("(2R,3R,4S,5R,6R)-2-(hydroxymethyl)-6-methoxyoxane-3,4,5-triol", 5, 0, "sugar ring"),  # methyl glucoside
    ("(2R,3S,4S,5R)-2-(hydroxymethyl)oxolane-3,4,5-triol", None, 0, "sugar ring"),
    # --- nucleosides / nucleobases ---
    ("adenine", 0, 0, "nucleobase"),
    ("guanine", 0, 0, "nucleobase"),
    ("cytosine", 0, 0, "nucleobase"),
    ("thymine", 0, 0, "nucleobase"),
    ("uracil", 0, 0, "nucleobase"),
    ("9H-purin-6-amine", 0, 0, "nucleobase"),
    ("5-methylpyrimidine-2,4(1H,3H)-dione", 0, 0, "nucleobase"),
    ("(2R,3R,4S,5R)-2-(6-aminopurin-9-yl)-5-(hydroxymethyl)oxolane-3,4-diol", 4, 0, "nucleoside"),  # adenosine
    ("(2R,3S,5R)-5-(6-aminopurin-9-yl)-2-(hydroxymethyl)oxolan-3-ol", 3, 0, "nucleoside"),  # deoxyadenosine
    ("1-[(2R,4S,5R)-4-hydroxy-5-(hydroxymethyl)oxolan-2-yl]-5-methylpyrimidine-2,4-dione", 3, 0, "nucleoside"),  # thymidine
    ("1-[(2R,3R,4S,5R)-3,4-dihydroxy-5-(hydroxymethyl)oxolan-2-yl]pyrimidine-2,4-dione", 4, 0, "nucleoside"),  # uridine
    ("adenosine", 4, 0, "nucleoside"),
    ("thymidine", 3, 0, "nucleoside"),
    # --- terpenes / natural products ---
    ("2-methylbuta-1,3-diene", 0, 0, "terpene"),
    ("(4R)-1-methyl-4-(prop-1-en-2-yl)cyclohex-1-ene", 1, 0, "terpene"),
    ("(1R,5R)-2,6,6-trimethylbicyclo[3.1.1]hept-2-ene", 2, 0, "terpene"),  # alpha-pinene
    ("(1S,5S)-2,6,6-trimethylbicyclo[3.1.1]hept-2-ene", 2, 0, "terpene"),
    ("(1R,5R)-6,6-dimethyl-2-methylidenebicyclo[3.1.1]heptane", 2, 0, "terpene"),  # beta-pinene
    ("(1R,2S,5R)-2-isopropyl-5-methylcyclohexan-1-ol", 3, 0, "terpene"),  # menthol
    ("(2R,5R)-2-methyl-5-(prop-1-en-2-yl)cyclohexan-1-one", None, 0, "terpene"),
    ("(2S,5R)-2-methyl-5-(prop-1-en-2-yl)cyclohexan-1-one", 2, 0, "terpene"),  # dihydrocarvone
    ("(5R)-2-methyl-5-(prop-1-en-2-yl)cyclohex-2-en-1-one", 1, 0, "terpene"),  # (R)-carvone
    ("(5S)-2-methyl-5-(prop-1-en-2-yl)cyclohex-2-en-1-one", 1, 0, "terpene"),  # (S)-carvone
    ("(2E)-3,7-dimethylocta-2,6-dien-1-ol", 0, 1, "terpene"),  # geraniol
    ("(2Z)-3,7-dimethylocta-2,6-dien-1-ol", 0, 1, "terpene"),  # nerol
    ("(3R)-3,7-dimethylocta-1,6-dien-3-ol", 1, 0, "terpene"),  # linalool
    ("(3S)-3,7-dimethylocta-1,6-dien-3-ol", 1, 0, "terpene"),
    ("(2E)-3,7-dimethylocta-2,6-dienal", 0, 1, "terpene"),  # geranial
    ("(3R)-3,7-dimethyloct-6-en-1-ol", 1, 0, "terpene"),  # citronellol
    ("(1R,2R,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-ol", 3, 0, "terpene"),  # borneol
    ("(1S,2R,4S)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-ol", 3, 0, "terpene"),
    ("(1R,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one", 2, 0, "terpene"),
    ("1,3,3-trimethyl-2-oxabicyclo[2.2.2]octane", 0, 0, "terpene"),  # eucalyptol
    ("(1S,2S,3S,5R)-2,6,6-trimethylbicyclo[3.1.1]heptan-3-ol", 4, 0, "terpene"),  # isopinocampheol
    ("(1R,4aS,8aS)-1,4a-dimethyl-6-methylidene-2,3,4,5,7,8-hexahydro-1H-naphthalene", None, 0, "terpene"),
    ("(6E,10E,14E,18E)-2,6,10,15,19,23-hexamethyltetracosa-2,6,10,14,18,22-hexaene", 0, 4, "terpene"),  # squalene
    ("(2E,4E,6E,8E)-3,7-dimethyl-9-(2,6,6-trimethylcyclohexen-1-yl)nona-2,4,6,8-tetraenoic acid", 0, 4, "terpene"),  # retinoic acid
    ("(2E,4E,6E,8E)-3,7-dimethyl-9-(2,6,6-trimethylcyclohexen-1-yl)nona-2,4,6,8-tetraen-1-ol", 0, 4, "terpene"),  # retinol
    # --- steroids ---
    ("cholesterol", 8, 0, "steroid"),
    ("(3S,8S,9S,10R,13R,14S,17R)-10,13-dimethyl-17-[(2R)-6-methylheptan-2-yl]-2,3,4,7,8,9,11,12,14,15,16,17-dodecahydro-1H-cyclopenta[a]phenanthren-3-ol", 8, 0, "steroid"),
    ("(8R,9S,10R,13S,14S,17S)-17-hydroxy-10,13-dimethyl-1,2,6,7,8,9,11,12,14,15,16,17-dodecahydrocyclopenta[a]phenanthren-3-one", 6, 0, "steroid"),
    ("(8R,9S,13S,14S,17S)-13-methyl-6,7,8,9,11,12,14,15,16,17-decahydrocyclopenta[a]phenanthrene-3,17-diol", 5, 0, "steroid"),
    ("(8S,9S,10R,11S,13S,14S,17R)-11,17-dihydroxy-17-(2-hydroxyacetyl)-10,13-dimethyl-1,2,6,7,8,9,11,12,14,15,16-undecahydrocyclopenta[a]phenanthren-3-one", None, 0, "steroid"),
    ("5alpha-androstane", 6, 0, "steroid"),
    ("(5S,8R,9S,10S,13R,14S)-10,13-dimethyl-2,3,4,5,6,7,8,9,11,12,14,15,16,17-tetradecahydro-1H-cyclopenta[a]phenanthrene", 6, 0, "steroid"),
    # --- drugs / pharma ---
    ("2-acetoxybenzoic acid", 0, 0, "drug"),
    ("paracetamol", 0, 0, "drug"),
    ("caffeine", 0, 0, "drug"),
    ("(S)-nicotine", 1, 0, "drug"),
    ("(R)-nicotine", 1, 0, "drug"),
    ("morphine", 5, 0, "drug"),
    ("codeine", 5, 0, "drug"),
    ("(2S,5R,6R)-3,3-dimethyl-7-oxo-6-[(2-phenylacetyl)amino]-4-thia-1-azabicyclo[3.2.0]heptane-2-carboxylic acid", 3, 0, "drug"),
    ("(S)-1-(isopropylamino)-3-(naphthalen-1-yloxy)propan-2-ol", 1, 0, "drug"),
    ("(3S)-3-(1,3-dioxoisoindol-2-yl)piperidine-2,6-dione", 1, 0, "drug"),
    ("(R)-adrenaline", 1, 0, "drug"),
    ("(R)-4-[1-hydroxy-2-(methylamino)ethyl]benzene-1,2-diol", 1, 0, "drug"),
    ("(S)-2-(2-chlorophenyl)-2-(methylamino)cyclohexan-1-one", 1, 0, "drug"),
    ("(S)-ibuprofen", 1, 0, "drug"),
    ("(2S)-2-(6-methoxynaphthalen-2-yl)propanoic acid", 1, 0, "drug"),
    ("(R)-5-(1,2-dithiolan-3-yl)pentanoic acid", 1, 0, "drug"),
    ("(3S)-3-(aminomethyl)-5-methylhexanoic acid", 1, 0, "drug"),
    ("(R)-lipitor", None, None, "drug-skip"),  # not a systematic/trivial name OPSIN knows
    ("(3R,5R)-7-[2-(4-fluorophenyl)-3-phenyl-4-(phenylcarbamoyl)-5-propan-2-ylpyrrol-1-yl]-3,5-dihydroxyheptanoic acid", 2, 0, "drug"),
    ("(2S)-1-[(2S)-2-methyl-3-sulfanylpropanoyl]pyrrolidine-2-carboxylic acid", 2, 0, "drug"),
    ("(S)-dopa", 1, 0, "drug"),
    ("(S)-2-amino-3-[4-(4-hydroxy-3,5-diiodophenoxy)-3,5-diiodophenyl]propanoic acid", 1, 0, "drug"),
    ("(3R,5aS,6R,8aS,9R,12S,12aR)-3,6,9-trimethyloctahydro-3,12-epoxy-12H-pyrano[4,3-j]-1,2-benzodioxepin-10(3H)-one", None, 0, "drug"),
    ("ethyl (3R,4R,5S)-4-acetamido-5-amino-3-(pentan-3-yloxy)cyclohex-1-ene-1-carboxylate", 3, 0, "drug"),
    ("biotin", 3, 0, "drug"),
    ("(2R,3S,4S)-2,3,4,5-tetrahydroxypentyl", None, None, "skip-fragment"),
    ("(2R)-2,5,7,8-tetramethyl-2-[(4R,8R)-4,8,12-trimethyltridecyl]-3,4-dihydrochromen-6-ol", 3, 0, "vitamin"),
    ("folic acid", 1, 0, "vitamin"),
    ("pyridoxine", 0, 0, "vitamin"),
    ("nicotinamide", 0, 0, "vitamin"),
    ("(3S,5Z,7E)-9,10-secocholesta-5,7,10(19)-trien-3-ol", None, None, "vitamin-skip"),
    # --- alkaloids / other natural products ---
    ("(2S)-2-propylpiperidine", 1, 0, "alkaloid"),
    ("(S)-(-)-nicotine", 1, 0, "alkaloid"),
    ("(2S)-2-amino-3-(1H-indol-3-yl)propanoic acid", 1, 0, "alkaloid"),
    # --- lipids / long chain ---
    ("octadecane", 0, 0, "lipid"),
    ("hexacosane", 0, 0, "lipid"),
    ("(9Z,12Z,15Z)-octadeca-9,12,15-trienoic acid", 0, 3, "lipid"),  # alpha-linolenic
    ("(4Z,7Z,10Z,13Z,16Z,19Z)-docosa-4,7,10,13,16,19-hexaenoic acid", 0, 6, "lipid"),  # DHA
    ("(5Z,8Z,11Z,14Z,17Z)-icosa-5,8,11,14,17-pentaenoic acid", 0, 5, "lipid"),  # EPA
    ("(9E,11E)-octadeca-9,11-dienoic acid", 0, 2, "lipid"),
    ("(2S)-2,3-dihydroxypropyl hexadecanoate", 1, 0, "lipid"),
    ("(2R)-2,3-dihydroxypropyl (9Z)-octadec-9-enoate", 1, 1, "lipid"),
    ("propane-1,2,3-triyl tri(octadecanoate)", 0, 0, "lipid"),
    ("(12R)-12-hydroxyoctadecanoic acid", 1, 0, "lipid"),
    ("(9R,10S)-9,10-dihydroxyoctadecanoic acid", 2, 0, "lipid"),
    ("(5S,6R,7E,9E,11Z,14Z)-5,6-dihydroxyicosa-7,9,11,14-tetraenoic acid", 2, 4, "lipid"),  # LTB4-ish
    ("(5Z,8Z,11Z,14Z)-N-(2-hydroxyethyl)icosa-5,8,11,14-tetraenamide", 0, 4, "lipid"),  # anandamide
    ("(2R)-2-[(3R,5S,7S,10S,13R)-3-hydroxy...", None, None, "lipid-skip"),  # intentionally truncated
    # --- charged / salts / isotopes / unusual ---
    ("sodium chloride", 0, 0, "salt"),
    ("sodium acetate", 0, 0, "salt"),
    ("potassium (2R,3R)-2,3-dihydroxybutanedioate", 2, 0, "salt"),
    ("tetramethylammonium chloride", 0, 0, "salt"),
    ("(S)-1-phenylethanaminium chloride", 1, 0, "salt"),
    ("(2R)-2-hydroxypropanoate", 1, 0, "ion"),
    ("methylammonium", 0, 0, "ion"),
    ("acetate", 0, 0, "ion"),
    ("tetrafluoroborate", 0, 0, "ion"),
    ("deuteriomethane", 0, 0, "isotope"),
    ("trideuteriomethanol", 0, 0, "isotope"),
    ("(R)-1-deuterioethanol", 1, 0, "isotope"),  # H/D chirality
    ("(S)-1-deuterioethanol", 1, 0, "isotope"),
    ("(R)-1-deuterio-1-fluoroethane", 1, 0, "isotope"),
    ("(13C)methane", 0, 0, "isotope"),
    ("2H2O", None, None, "isotope-skip"),
    ("water", 0, 0, "inorganic"),
    ("ammonia", 0, 0, "inorganic"),
    ("hydrogen peroxide", 0, 0, "inorganic"),
    ("carbon dioxide", 0, 0, "inorganic"),
    ("sulfuric acid", 0, 0, "inorganic"),
    ("nitric acid", 0, 0, "inorganic"),
    ("hydrazine", 0, 0, "inorganic"),
    ("hydroxylamine", 0, 0, "inorganic"),
    ("phosphine", 0, 0, "inorganic"),
    ("silane", 0, 0, "inorganic"),
    ("borane", 0, 0, "inorganic"),
    ("cyanide", 0, 0, "inorganic"),
    # --- nitrogen stereocentres / quaternary / other heteroatom chirality ---
    ("(S)-ethyl(methyl)(propyl)(phenyl)phosphanium", None, 0, "P-chiral"),
    ("(R)-ethyl methyl sulfoxide", 1, 0, "S-chiral"),
    ("(S)-ethyl methyl sulfoxide", 1, 0, "S-chiral"),
    ("(R)-methyl phenyl sulfoxide", 1, 0, "S-chiral"),
    ("(S)-methyl 4-methylphenyl sulfoxide", 1, 0, "S-chiral"),
    ("(S)-ethyl methyl sulfinate", None, 0, "S-chiral"),
    # --- multi-element / polyfunctional / large ---
    ("2-amino-2-(hydroxymethyl)propane-1,3-diol", 0, 0, "poly"),
    ("(2S,3S,4S,5R,6R)-6-[(2S,3R,4S,5S,6R)-4,5-dihydroxy-2-(hydroxymethyl)-6-methoxyoxan-3-yl]oxy-3,4,5-trihydroxyoxane-2-carboxylic acid", None, 0, "poly"),
    ("(2R,3R,4S,5S,6R)-2-[(2S,3S,4S,5R)-3,4-dihydroxy-2,5-bis(hydroxymethyl)oxolan-2-yl]oxy-6-(hydroxymethyl)oxane-3,4,5-triol", 9, 0, "poly"),  # sucrose
    ("(2R,3S,4R,5R,6S)-2-(hydroxymethyl)-6-[(2R,3S,4R,5R,6R)-4,5,6-trihydroxy-2-(hydroxymethyl)oxan-3-yl]oxyoxane-3,4,5-triol", 10, 0, "poly"),
    ("N-[(2S,3R,4R,5S,6R)-2,4,5-trihydroxy-6-(hydroxymethyl)oxan-3-yl]acetamide", 5, 0, "poly"),  # GlcNAc
    ("2,2'-bipyridine", 0, 0, "poly"),
    ("1,1'-biphenyl-2,2'-diol", 0, 0, "poly"),
    ("1,10-phenanthroline", 0, 0, "poly"),
    ("ethylenediaminetetraacetic acid", 0, 0, "poly"),
    ("2-[2-[bis(carboxymethyl)amino]ethyl-(carboxymethyl)amino]acetic acid", 0, 0, "poly"),
    ("tris(2-aminoethyl)amine", 0, 0, "poly"),
    ("1,3,5,7-tetraazatricyclo[3.3.1.1~3,7~]decane", 0, 0, "poly"),
    ("tetraphenylmethane", 0, 0, "poly"),
    ("triphenylmethanol", 0, 0, "poly"),
    ("2,2,6,6-tetramethylpiperidin-1-yl)oxidanyl", None, None, "skip-radical"),
    ("pentacene", 0, 0, "aromatic"),
    ("coronene", 0, 0, "aromatic"),
    ("porphyrin", 0, 0, "macrocycle"),
    ("cyclododeca-1,5,9-triene", 0, 0, "macrocycle"),
    ("(1E,5E,9E)-cyclododeca-1,5,9-triene", 0, 3, "macrocycle"),
    ("(1Z,5E,9E)-cyclododeca-1,5,9-triene", 0, 3, "macrocycle"),
    ("cyclooctatetraene", 0, 0, "macrocycle"),
    ("[18]annulene", 0, 0, "macrocycle"),
    ("oxacyclohexadecan-2-one", 0, 0, "macrocycle"),
    ("(4R)-4-methyloxacyclohexadecan-2-one", 1, 0, "macrocycle"),
    ("(4S)-4-methyloxacyclohexadecan-2-one", 1, 0, "macrocycle"),
    # --- explicit SMILES inputs ---
    ("C[C@H](N)C(=O)O", 1, 0, "smiles"),
    ("C[C@@H](N)C(=O)O", 1, 0, "smiles"),
    ("C/C=C/C", 0, 1, "smiles"),
    ("C/C=C\\C", 0, 1, "smiles"),
    ("F/C=C/F", 0, 1, "smiles"),
    ("C[C@H](Br)[C@@H](C)Br", 2, 0, "smiles"),
    ("O[C@H]1CCCC[C@@H]1O", 2, 0, "smiles"),
    ("c1ccccc1", 0, 0, "smiles"),
    ("CC(C)(C)C", 0, 0, "smiles"),
    ("C1CC2CCC1C2", 0, 0, "smiles"),
    ("OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O", 5, 0, "smiles"),
    ("CC(=O)Oc1ccccc1C(=O)O", 0, 0, "smiles"),
    ("[Na+].[Cl-]", 0, 0, "smiles"),
    ("C[N+](C)(C)C", 0, 0, "smiles"),
    ("CC[S@](=O)C", 1, 0, "smiles"),
    ("CC[S@@](=O)C", 1, 0, "smiles"),
    ("C[C@H](F)[2H]", 1, 0, "smiles"),
    # --- systematic names for drugs OPSIN has no trivial entry for ---
    ("methyl (1R,2R,3S,5S)-3-benzoyloxy-8-methyl-8-azabicyclo[3.2.1]octane-2-carboxylate", 4, 0, "drug"),  # cocaine
    ("4-hydroxy-3-[(1S)-3-oxo-1-phenylbutyl]chromen-2-one", 1, 0, "drug"),  # warfarin
    ("(2S)-N-methyl-1-phenylpropan-2-amine", 1, 0, "drug"),  # methamphetamine
    ("7-chloro-1-methyl-5-phenyl-3H-1,4-benzodiazepin-2-one", 0, 0, "drug"),  # diazepam
    ("3-(diaminomethylidene)-1,1-dimethylguanidine", 0, 0, "drug"),  # metformin
    ("2-(diethylamino)-N-(2,6-dimethylphenyl)acetamide", 0, 0, "drug"),  # lidocaine
    ("(2S)-2-[4-(2-methylpropyl)phenyl]propanoic acid", 1, 0, "drug"),
    ("(1S)-2-(tert-butylamino)-1-[4-hydroxy-3-(hydroxymethyl)phenyl]ethanol", 1, 0, "drug"),  # salbutamol
    ("(2S)-1-[(2S)-2-methyl-3-sulfanylpropanoyl]pyrrolidine-2-carboxylic acid", 2, 0, "drug"),  # captopril
    ("(2S)-2-amino-3-(3,4-dihydroxyphenyl)propanoic acid", 1, 0, "drug"),  # levodopa
    ("(2S)-2-amino-3-[4-(4-hydroxy-3,5-diiodophenoxy)-3,5-diiodophenyl]propanoic acid", 1, 0, "drug"),  # levothyroxine
    ("(4R)-4-methyl-1-oxa-cyclohexadecan-2-one", None, None, "skip"),
    ("(5R)-5-(1,2-dithiolan-3-yl)pentanoic acid", None, None, "skip"),
    ("(3R)-5-(1,2-dithiolan-3-yl)pentanoic acid", 1, 0, "drug"),  # lipoic acid
    ("(2S)-2-(6-methoxynaphthalen-2-yl)propanoic acid", 1, 0, "drug"),  # naproxen
    ("(3S)-3-(aminomethyl)-5-methylhexanoic acid", 1, 0, "drug"),  # pregabalin
    ("(3R)-4-amino-3-(4-chlorophenyl)butanoic acid", 1, 0, "drug"),  # baclofen
    ("(2R)-2-propylpiperidine", 1, 0, "alkaloid"),  # coniine
    ("(2S)-2-propylpiperidine", 1, 0, "alkaloid"),
    ("6-chloro-N-methyl-1-phenyl... ", None, None, "skip"),
]

# Trivial or malformed names OPSIN does not know. They must be rejected cleanly.
UNSUPPORTED_NAMES: list[str] = [
    '18-crown-6',
    '(R)-limonene',
    '(S)-limonene',
    'testosterone',
    'estradiol',
    'progesterone',
    'cortisol',
    'cholic acid',
    'aspirin',
    '(4R,4aR,7S,7aR,12bS)-3-methyl-2,4,4a,7,7a,13-hexahydro-1H-4,12-methanobenzofuro[3,2-e]isoquinoline-7,9-diol',
    'cocaine',
    'atropine',
    'quinine',
    'penicillin G',
    'amoxicillin',
    '(S)-warfarin',
    '(R)-warfarin',
    '(S)-propranolol',
    '(R)-salbutamol',
    '(S)-thalidomide',
    '(R)-thalidomide',
    '(S)-ketamine',
    '(S)-omeprazole',
    '(S)-citalopram',
    '(S)-naproxen',
    '(R)-methamphetamine',
    '(S)-methamphetamine',
    '(R)-fluoxetine',
    '(S)-ofloxacin',
    '(S)-lansoprazole',
    '(R)-lipoic acid',
    '(S)-metoprolol',
    '(R)-baclofen',
    '(S)-pregabalin',
    'atorvastatin',
    'sildenafil',
    'diazepam',
    'metformin',
    'acetaminophen',
    'lidocaine',
    'nifedipine',
    '(S)-amlodipine',
    'captopril',
    'enalapril',
    'levodopa',
    'levothyroxine',
    'paclitaxel',
    'artemisinin',
    'oseltamivir',
    'remdesivir',
    'riboflavin',
    'alpha-tocopherol',
    'thiamine',
    'menadione',
    '(2E,4E,6E,8E)-retinal',
    'cholecalciferol',
    '(S)-coniine',
    '(R)-coniine',
    'strychnine',
    '(S)-hyoscyamine',
    '(S)-scopolamine',
    '(+)-limonene',
    '(R)-carvone',
    '(S)-carvone',
    'sucrose',
    'maltose',
    'hexamethylenetetramine',
]


# Names that must be REJECTED (parse failure) or produce an unspecified-stereo flag.
INVALID: list[str] = [
    "",
    "   ",
    "not a chemical",
    "asdfghjkl",
    "benzene-1,2,3,4,5,6,7-heptol",
    "cyclohexane-1,2,3,4,5,6,7-heptamethyl",
    "(2Q)-butan-2-ol",
    "hexane-7-ol",
    "3-methylbut-3-yne-3-ol",
    "chloro",
    "methylene blue blue",
    "SELECT * FROM users",
    "<script>alert(1)</script>",
    "C(C)(C)(C)(C)C",  # pentavalent carbon SMILES
    "C1CC",  # unclosed ring
]

IMPOSSIBLE_STEREO: list[str] = [
    "(1S,4R)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one",
    "(1R,4S)-1,7,7-trimethylbicyclo[2.2.1]heptan-2-one",
    "(1R,5S)-2,6,6-trimethylbicyclo[3.1.1]hept-2-ene",
    "(1R,4R)-bicyclo[2.2.1]heptan-2-one",
    "(1S,2S,4R)-2-methylbicyclo[2.2.1]heptane",
    "(1R,2S,4R)-bicyclo[2.2.1]heptan-2-ol",
]

# Fully unspecified names: must succeed but flag unspecified stereo.
UNSPECIFIED: list[tuple[str, int]] = [
    ("butan-2-ol", 1),
    ("2-methylcyclohexan-1-ol", 2),
    ("but-2-ene", 0),
    ("2,3-dibromobutane", 2),
    ("ibuprofen", 1),
    ("1,2-dimethylcyclohexane", 2),
    ("hexa-2,4-dienoic acid", 0),
    ("(2R)-2,3-dibromobutane", 2),  # one given, one missing
    ("(2E)-hexa-2,4-diene", 0),
    ("menthol", 3),
    ("2-butanol", 1),
    ('3-ethyl-2-methylhexane', 1),
    ('2-hydroxypropanoic acid', 1),
    ('nicotine', 1),
    ('lactose', 1),
    ('(+)-camphor', 2),
    ('(-)-menthol', 3),
    ('(-)-nicotine', 1),
    ('decahydronaphthalene', 2),
    ('bicyclo[4.4.0]decane', 2),
    ('(R)-[(2S,4S,5R)-5-ethenyl-1-azabicyclo[2.2.2]octan-2-yl]-(6-methoxyquinolin-4-yl)methanol', 1),
]

# Names whose stereo descriptor OPSIN cannot place. They build without it and carry a warning.
STEREO_IGNORED: list[str] = [
    '(2R,4S)-2,4-dimethylhexane',
    '(E)-N-phenylmethanimine',
    '(R)-N-ethyl-N-methylpropan-1-aminium',
    '(R)-methylphenylphosphinic acid',
    '(4aR,8aR)-decahydronaphthalene',
    '(S)-tert-butyl(methyl)phosphane oxide',
    '(R)-1-ethyl-1-methylpiperidin-1-ium',
    '(4aR,8aS)-decahydronaphthalene',
    '(1R,3R)-cyclobutane-1,3-diol',
    '(1R,2R,3R)-2-methylcyclopropane-1,3-dicarboxylic acid',
    '(R)-1-methyl-1-propylpyrrolidin-1-ium',
]
