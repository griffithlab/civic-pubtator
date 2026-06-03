#===================================================
# BioCreative V CDR subtask A - Disease Named Entity Recognition and Normalization (DNER) 
# Evaluation for Disease Recognition/Normalization & CID Relation Extraction
# Format: PubTator http://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/PubTator/
#===================================================

sub round
{
  my($value,$rank) = @_;
  if($value>0){
    return int($value * 10**$rank + 0.5) / 10**$rank;
  }else{
    return int($value * 10**$rank - 0.4 )/ 10**$rank;
  }
}

sub Evaluation
{
	my ($Gold)= $_[0];
	my ($Annotation)= $_[1];
	my ($EvaluationType)= $_[2];
	
	my %Gene2Homoid=();
	open input,"<Dictionary/Gene2Homoid.txt";
	while(<input>)
	{
		my $tmp=$_;
		$tmp=~s/[\n\r]//g;
		if($tmp=~/^([0-9]+)	([0-9]+)/)
		{
			my $entrez_id=$1;
			my $homo_id=$2;
			$Gene2Homoid{$entrez_id}=$homo_id;
		}
	}
	close input; 
	
	my %correctedid=();
	$corrected{"823741"}="832352";
	
	my %gold_hash=();
	open input,"<$Gold";
	while(<input>)
	{
		my $tmp=$_;
		$tmp=~s/[\n\r]//g;
		if($EvaluationType eq "relation" && $tmp=~/^([0-9]+)	CID	([^\t]+)	([^\t]+)/)
		{
			my $pmid=$1;
			my $chem=$2;
			my $dis=$3;
			$gold_hash{$pmid."\t".$chem."\t".$dis}=1;
		}
		elsif($tmp=~/^([0-9]+)	([0-9]+)	([0-9]+)	([^\t]+)	(Gene|GENERIF|STARGENE)	([^\t]+)/)
		{
			my $pmid=$1;
			my $start=$2;
			my $last=$3;
			my $ids=$6;
			
			if($EvaluationType eq "id" || $EvaluationType eq "Gene2Homoid" || $EvaluationType eq "TaxonomyID")
			{
				if($ids ne "-1" && $ids ne "")
				{
					foreach my $id(split(/[\|\+\,\;]/,$ids))
					{
						if($EvaluationType eq "TaxonomyID")
						{
							my $taxid="9606";
							if($id=~/\((Species|Tax):([0-9]+)\)/)
							{
								$taxid=$2;
							}

							$gold_hash{$pmid."\t".$start."\t".$taxid}=1;
						}
						else
						{
							$id=~s/\((Species|Tax):[0-9]+\)//g;
							
							if($EvaluationType eq "Gene2Homoid")
							{
								if(exists $Gene2Homoid{$id})
								{
									$id=$Gene2Homoid{$id};
									$gold_hash{$pmid."\t".$id}=$gold_hash{$pmid."\t".$id}.$mention."\t";
								}
								else
								{
									$gold_hash{$pmid."\t".$id}=$gold_hash{$pmid."\t".$id}.$mention."\t";
								}
							}
							else
							{
								$gold_hash{$pmid."\t".$id}=$gold_hash{$pmid."\t".$id}.$mention."\t";
							}
						}
					}
				}
			}
			elsif($EvaluationType eq "mention")
			{
				$gold_hash{$pmid."\t".$start."\t".$last}=1;
			}
		}
		elsif($tmp=~/^([0-9]+)	([0-9]+)	([0-9]+)	([^\t]+)	(Gene|GENERIF|STARGENE)/)
		{
			my $pmid=$1;
			my $start=$2;
			my $last=$3;
			
			if($EvaluationType eq "mention")
			{
				$gold_hash{$pmid."\t".$start."\t".$last}=1;
			}
		}
	}
	close input;
	
	$count=0;
	my %result_hash=();
	#open output,">".$Annotation.".rev";
	my %pmid_hash=();
	open input,"<$Annotation";
	while(<input>)
	{
		my $tmp=$_;
		$tmp=~s/[\n\r]//g;
		if($tmp=~/^([0-9]+)\|/)
		{
			my $pmid=$1;
			$pmid_hash{$pmid}=1;
		}
		elsif($EvaluationType eq "relation" && $tmp=~/^([0-9]+)	CID	([^\t]+)	([^\t]+)/)
		{
			my $pmid=$1;
			my $chem=$2;
			my $dis=$3;
			$result_hash{$pmid."\t".$chem."\t".$dis}=1;
		}
		elsif($tmp=~/^([0-9]+)	([0-9]+)	([0-9]+)	([^\t]+)	(Gene|Protein)	([^\t]+)/i)
		{
			my $pmid=$1;
			my $start=$2;
			my $last=$3;
			my $mention=$4;
			my $ids=$6;
			$pmid_hash{$pmid}=1;
			
			my $resultid="";
			if($EvaluationType eq "id" || $EvaluationType eq "Gene2Homoid" || $EvaluationType eq "TaxonomyID")
			{
				#
				# Left:6239|*172659-20748
				# Left:9606|9353-3516,6586-2303
				#
				if($ids=~/^(Left|Right|Focus|Prefix|Tax)\:(9606)\|(.+)$/) #[0-9]+
				{
					my $tax_id=$2;
					$ids=$3;
					#take all
					foreach my $id(split(",",$ids))
					{
						$id=~s/^\*([0-9]+).*$/$1/g;
						if($EvaluationType eq "Gene2Homoid")
						{
							if(exists $Gene2Homoid{$id})
							{
								$id=$Gene2Homoid{$id};
								$result_hash{$pmid."\t".$id}=$result_hash{$pmid."\t".$id}.$mention."\t";
							}
							else
							{
								$result_hash{$pmid."\t".$id}=$result_hash{$pmid."\t".$id}.$mention."\t";
							}
						}
						else
						{
							$result_hash{$pmid."\t".$id}=$result_hash{$pmid."\t".$id}.$mention."\t";
						}
					}
					## only one
					#if($ids=~/\*([0-9]+)/)
					#{
					#	$result_hash{$pmid."\t".$1}=1;
					#}
					#elsif($ids=~/^([0-9]+)/)
					#{
					#	$result_hash{$pmid."\t".$1}=1;
					#}
				}
				elsif($ids=~/^(Left|Right|Focus|Prefix|Tax)\:([0-9]+)/) #[0-9]+
				{
					if($EvaluationType eq "TaxonomyID")
					{
						my $taxid=$2;
						$result_hash{$pmid."\t".$start."\t".$taxid}=1;
					}
				}
				else
				{
					$ids=~s/NCBIGene://g;
					my @split_id=split(/[;,]/,$ids);
					foreach my $id(@split_id)
					{
						if($EvaluationType eq "Gene2Homoid")
						{
							if(exists $Gene2Homoid{$id})
							{
								$id=$Gene2Homoid{$id};
								$result_hash{$pmid."\t".$id}=$mention;
							}
							else
							{
								$result_hash{$pmid."\t".$id}=$mention;
							}
						}
						else
						{
							$result_hash{$pmid."\t".$id}=$mention;
						}
						
						if(exists $gold_hash{$pmid."\t".$id})
						{
							$resultid="!".$resultid.$id.",";
						}
						else
						{
							$resultid=$resultid.$id.",";
						}
					}
				}
			}
			elsif($EvaluationType eq "mention")
			{
				$result_hash{$pmid."\t".$start."\t".$last}=1;
				$count++;
			}
		}
		elsif($tmp=~/^([0-9]+)	([0-9]+)	([0-9]+)	([^\t]+)	(Gene|Protein)/i)
		{
			my $pmid=$1;
			my $start=$2;
			my $last=$3;
			
			if($EvaluationType eq "mention")
			{
				$result_hash{$pmid."\t".$start."\t".$last}=1;
				$count++;
			}
			#print output $tmp."\n";
		}
		else
		{
			#print output $tmp."\n";
		}
	}
	close input;
	close output;
	#print $count."\n";
	
	open FP,">FP.txt";
	my $TP=0;my $FN=0;my $FP=0;
	foreach my $gold (keys %gold_hash)
	{
		if($gold=~/^([^\t]+)/)
		{
			if(exists $pmid_hash{$1})
			{
				if(exists $result_hash{$gold})
				{
					$TP++;
				}
				else
				{
					#print FN $gold."\t".$gold_hash{$gold}."\n";
					$FN++;
				}
			}
		}
	}
	
	foreach my $result (keys %result_hash)
	{
		if($result=~/^([^\t]+)/)
		{
			if(exists $pmid_hash{$1})
			{
				if(exists $gold_hash{$result})
				{
					#$TP++;
				}
				else
				{
					print FP $result."\t".$result_hash{$result}."\n";
					$FP++;
				}
			}
		}
	}
	close FP;
	
	my $P=$TP/($FP+$TP);
	my $R=$TP/($FN+$TP);
	my $F=$P*$R*2/($P+$R);
	$P = round($P , 4);
	$R = round($R , 4);
	$F = round($F , 4);
	#print "TP: ".$TP."\n";
	#print "FP: ".$FP."\n";
	#print "FN: ".$FN."\n";
	#print "Precision: ".$P."\n";
	#print "Recall: ".$R."\n";
	#print "F-score: ".$F."\n";
	print $Annotation."\t".$EvaluationType."\t".$TP."\t".$FP."\t".$FN."\t".$P."\t".$R."\t".$F."\n";
}

sub main
{
	my $Gold=$ARGV[0];
	my $Annotation=$ARGV[1];
	my $EvaluationType=$ARGV[2];
	if($Gold eq "" || $Annotation eq "" || $EvaluationType!~/^(mention|id|relation|Gene2Homoid|TaxonomyID)$/)
	{
		print "perl Evaluation.pl [Gold] [Annotation] [Evaluation Type:mention|id|relation|Gene2Homoid|TaxonomyID]\n";
	}
	else
	{
		&Evaluation($Gold,$Annotation,$EvaluationType);
	}
}

main();