wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz
gunzip taxdump.tar.gz
mkdir taxdump
mv taxdump.tar taxdump
cd taxdump
tar -xvf taxdump.tar
grep "genbank common name" names.dmp | cut -d "|" -f 1,2 | cut -f 1,3 > ../taxon-id_common_name_map.tsv
cd ..
rm -fr taxdump

