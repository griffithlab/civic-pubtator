package tmVarlib;
//
// tmVar - Java version
//

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

import javax.xml.stream.XMLStreamException;

public class CorrespondGene
{
	public static void main(String [] args) throws IOException, InterruptedException, XMLStreamException, SQLException 
	{
		String InputFolder= "input";
		String OutputFolder= "output";
		int suffixNum=-1;
		if(args.length<2)
		{
			System.out.println("\n$ java -Xmx10G -Xms10G -jar CorrespondGene.jar [InputFolder:input] [OutputFolder:output] [suffixNum]\n");
		}
		else
		{
			InputFolder= args[0];
			OutputFolder= args[1];
			if(args.length>=3)
			{
				suffixNum=Integer.parseInt(args[2]);
			}
		}
		
		double startTime,endTime,totTime;
		startTime = System.currentTimeMillis();//start time
		
		File folder = new File(InputFolder); // Files in the InputFolder
		File[] listOfFiles = folder.listFiles();
		for (int x = 0; x < listOfFiles.length; x++)
		{
			if (listOfFiles[x].isFile()) 
			{
				String InputFile = listOfFiles[x].getName();
				String fileSet="";
				int fileSuffix=-1;
				Pattern ptmp = Pattern.compile("^([0-9]+)");
				Matcher mtmp = ptmp.matcher(InputFile);
				if(mtmp.find())
				{
					fileSet=mtmp.group(1);
					if(fileSet.length()>=2)
					{
						fileSet=fileSet.substring(fileSet.length()-2);
					}
					fileSuffix=Integer.parseInt(fileSet);
				}
				
				if(suffixNum==-1 || fileSuffix == suffixNum)
				{
					File f = new File(OutputFolder+"/"+InputFile);
					if(f.exists() && !f.isDirectory()) 
					{ 
						System.out.println(OutputFolder+"/"+InputFile+" - Done. (The output file exists)");
					}
					else
					{
						BioCConverter BC= new BioCConverter();
						
						/*
						 * Format Check 
						 */
						String Format = "";
						String checkR=BC.BioCFormatCheck(InputFolder+"/"+InputFile);
						if(checkR.equals("BioC"))
						{
							Format = "BioC";
						}
						//else if(checkR.equals("PubTator"))
						//{
						//	Format = "PubTator";
						//}
						else
						{
							System.out.println("Input format is BioC-XML only.");
							System.exit(0);
						}
						
						System.out.print(InputFolder+"/"+InputFile+" - ("+Format+" format) : Processing ... \r");
						
						/*
						 * Blacklist Species
						 */
						HashMap<String,String> Blacklist_Species = new HashMap<String,String>();
						Blacklist_Species.put("255564", "ray");Blacklist_Species.put("11246", "brs");
						Blacklist_Species.put("9103", "Turkey");Blacklist_Species.put("76720", "Fisher");
						Blacklist_Species.put("11612", "insV"); 
						
						HashMap<String,ArrayList<String>> RS2Gene = new HashMap<String,ArrayList<String>>();
						
						BC.BioCReaderWithAnnotation(InputFolder+"/"+InputFile);
						
						for (int i = 0; i < BC.PMIDs.size(); i++) /** PMIDs : i */
						{
							String Pmid = BC.PMIDs.get(i);
							String FullText=" "; // not cover ref
							HashMap<String,HashMap<String,String>> GeneAnno = new HashMap<String,HashMap<String,String>>();
							HashMap<String,HashMap<String,String>> SpeciesAnno = new HashMap<String,HashMap<String,String>>();
							HashMap<String,HashMap<String,String>> VariationAnno = new HashMap<String,HashMap<String,String>>();
							HashMap<Integer,Integer> TablePassage=new HashMap<Integer,Integer>();
							HashMap<String,Integer> Gene2Num=new HashMap<String,Integer>(); 
							for (int j = 0; j < BC.PassageNames.get(i).size(); j++) /** Paragraphs : j */
							{
								String PassageName= BC.PassageNames.get(i).get(j); // Passage name
								int PassageOffset = BC.PassageOffsets.get(i).get(j); // Passage offset
								String PassageContext = BC.PassageContexts.get(i).get(j); // Passage context
								ArrayList<String> Annotation = BC.Annotations.get(i).get(j); // Annotation
								if(PassageName.toLowerCase().equals("table")) // table only allow backward check
								{
									TablePassage.put(j,PassageOffset);
								}
								if(!PassageName.toLowerCase().equals("ref")) // the paragraphs addition to "ref"
								{
									FullText=FullText+PassageContext+" ";
									for(int a=0;a<Annotation.size();a++)
									{
										String anno[]=Annotation.get(a).split("\t");
										String start=anno[0];
										String last=anno[1];
										String type=anno[3];
										String id="";
										if(anno.length==5){id=anno[4];}
										if(PassageContext.length()>=Integer.parseInt(last) && Integer.parseInt(start)>=0)
										{	
											String mention = PassageContext.substring(Integer.parseInt(start), Integer.parseInt(last));
											if(type.equals("Gene"))
											{
												if(!GeneAnno.containsKey(id))
												{
													GeneAnno.put(id, new HashMap<String,String>());
												}
												GeneAnno.get(id).put(j+"\t"+start+"\t"+last+"\t"+mention, "");
												if(Gene2Num.containsKey(id))
												{
													Gene2Num.put(id, Gene2Num.get(id)+1);
												}
												else
												{
													Gene2Num.put(id, 1);
												}
											}
											else if(type.equals("Species"))
											{
												if(!SpeciesAnno.containsKey(id))
												{
													SpeciesAnno.put(id, new HashMap<String,String>());
												}
												SpeciesAnno.get(id).put(j+"\t"+start+"\t"+last+"\t"+mention, "");
											}
											else if(type.matches("(ProteinMutation|DNAMutation)"))
											{
												if(!VariationAnno.containsKey(id))
												{
													VariationAnno.put(id, new HashMap<String,String>());
												}
												VariationAnno.get(id).put(j+"\t"+start+"\t"+last+"\t"+mention, "");
												
												ptmp = Pattern.compile(".*RS#:(.*)");
												mtmp = ptmp.matcher(id);
												if(mtmp.find())
												{
													VariationAnno.get(id).put("RS",mtmp.group(1));
												}
											}
										}
									}
								}
								else if(PassageName.toLowerCase().equals("ref")) // only the ref mentions also in the full text will be included
								{
									for(int a=0;a<Annotation.size();a++)
									{
										String anno[]=Annotation.get(a).split("\t");
										String start=anno[0];
										String last=anno[1];
										String type=anno[3];
										String id="";
										if(anno.length>4){id=anno[4];}
										
										if(PassageContext.length()>=Integer.parseInt(last) && Integer.parseInt(start)>=0)
										{
											String mention = PassageContext.substring(Integer.parseInt(start), Integer.parseInt(last));
											if(type.equals("Gene"))
											{
												if(!GeneAnno.containsKey(id))
												{
													GeneAnno.put(id, new HashMap<String,String>());
												}
												GeneAnno.get(id).put(j+"\t"+start+"\t"+last+"\t"+mention, "");
											}
											else if(type.matches("(ProteinMutation|DNAMutation)"))
											{
												String mention_tmp = mention.replaceAll("([\\W\\-\\_])", "\\\1");
												if(FullText.toLowerCase().matches(".*"+mention_tmp.toLowerCase()+".*"))
												{
													if(!VariationAnno.containsKey(id))
													{
														VariationAnno.put(id, new HashMap<String,String>());
													}
													VariationAnno.get(id).put(j+"\t"+start+"\t"+last+"\t"+mention, "");
													
													ptmp = Pattern.compile(".*RS#:(.*)");
													mtmp = ptmp.matcher(id);
													if(mtmp.find())
													{
														VariationAnno.get(id).put("RS",mtmp.group(1));
													}
												}
											}
										}
									}
								}
							}
							
							/*
							 *  find major Gene
							 */
							String MajorGene="";
							int MajorGene_Num=0;
							for(String Gene : Gene2Num.keySet())
							{
								if(Gene2Num.get(Gene)>MajorGene_Num)
								{
									MajorGene=Gene;
									MajorGene_Num=Gene2Num.get(Gene);
								}
							}
							
							for(String Varid : VariationAnno.keySet()) // variation id --> variation mentions
							{
								int ClosedDistance=10000;
								String ClosedGene="";
								String ClosedSpecies="";
								if(!VariationAnno.get(Varid).containsKey("RS"))
								{
									/*
									 * find closed gene
									 */
									for(String Geneid : GeneAnno.keySet())
									{
										for(String Varlocation : VariationAnno.get(Varid).keySet()) // variation mention
										{
											String Var_anno[]=Varlocation.split("\t");
											int Var_paragraph_id=Integer.parseInt(Var_anno[0]);
											int Var_start=Integer.parseInt(Var_anno[1]);
											int Var_last=Integer.parseInt(Var_anno[2]);
											String Var_mention=Var_anno[3];
											
											int SurroundText_start=0;
											int SurroundText_last=Var_last+100;
											if(Var_start>100){SurroundText_start=Var_start-100;}
											if((Var_last+100)>BC.PassageContexts.get(i).get(Var_paragraph_id).length()){SurroundText_last=BC.PassageContexts.get(i).get(Var_paragraph_id).length();}
											String SurroundText=BC.PassageContexts.get(i).get(Var_paragraph_id).substring(SurroundText_start, SurroundText_last);
											String Var_mention_tmp = Var_mention.replaceAll("([\\W\\-\\_])", "\\\1");
											ptmp = Pattern.compile(".*\\(([^\\)]*)"+Var_mention_tmp+"([^\\(]*)\\).*"); //if ....(...Var...).... ; re-assign offset for variations
											mtmp = ptmp.matcher(SurroundText);
											if(mtmp.find())
											{
												String pre=mtmp.group(1);
												for(String Genelocation : GeneAnno.get(Geneid).keySet())
												{
													String Gene_anno[]=Genelocation.split("\t");
													String Gene_mention=Gene_anno[3];
													Gene_mention=Gene_mention.replaceAll("([\\W\\-\\_])", ".");
													if(!pre.matches(".*"+Gene_mention+".*"))
													{
														Var_start=Var_start-pre.length();
														Var_last=Var_start;
														break;
													}
												}
											}
											
											for(String Genelocation : GeneAnno.get(Geneid).keySet())
											{
												String Gene_anno[]=Genelocation.split("\t");
												int Gene_paragraph_id=Integer.parseInt(Gene_anno[0]);
												int Gene_start=Integer.parseInt(Gene_anno[1]);
												int Gene_last=Integer.parseInt(Gene_anno[2]);
												String Gene_mention=Gene_anno[3];
												if(Var_paragraph_id == Gene_paragraph_id) // paragraph the same
												{
													if(Var_start>Gene_last) // ... Gene ... Var ...
													{
														if(ClosedDistance>(Var_start-Gene_last))
														{
															ClosedDistance=Var_start-Gene_last;
															ClosedGene=Geneid;
														}
													}
													else if(Gene_start>Var_last && (!TablePassage.containsKey(Var_paragraph_id))) // ... Var ... Gene ...
													{
														if(Var_last<0){Var_last=0;}
														String betweenString=BC.PassageContexts.get(i).get(Var_paragraph_id).substring(Var_last, Gene_start);
														Gene_mention=Gene_mention.replaceAll("[\\(\\)]", "\\.");
														if(!betweenString.matches(".*[a-z]\\. .*")) // Gene is in the next sentence
														{
															if(ClosedDistance>(Gene_start-Var_last))
															{
																ClosedDistance=Gene_start-Var_last;
																ClosedGene=Geneid;
															}
														}
													}
													else if(!TablePassage.containsKey(Var_paragraph_id))// overlap
													{
														if(ClosedDistance>0)
														{
															ClosedDistance=0;
															ClosedGene=Geneid;
														}
													}
												}
											}
										}
									}
									if(ClosedGene.equals(""))
									{
										ClosedGene=MajorGene;
									}
								}
								else //;RS#
								{
									String RSNum=VariationAnno.get(Varid).get("RS");
									ArrayList<String> Genes = new ArrayList<String>();
									if(RS2Gene.containsKey(RSNum))
									{
										Genes=RS2Gene.get(RSNum);
									}
									else
									{
										try 
										{
											URL url_Submit = new URL("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=snp&mode=xml&id=" + RSNum);
											HttpURLConnection conn_Submit = (HttpURLConnection) url_Submit.openConnection();
											conn_Submit.setDoOutput(true);
											conn_Submit.setRequestMethod("GET");
											int code = conn_Submit.getResponseCode();
											if(code == 200)
											{
												String STR="";
												String line="";
												BufferedReader br_Receive = new BufferedReader(new InputStreamReader(conn_Submit.getInputStream(), "UTF-8"));
												while((line = br_Receive.readLine()) != null)
												{
													STR=STR+line;
												}
												STR=STR.replaceAll("[\\r\\n]", "");
												ptmp = Pattern.compile("<FxnSet geneId=\"([0-9]+)\"");
												mtmp = ptmp.matcher(STR);
												while(mtmp.find())
												{
													Genes.add(mtmp.group(1));
												}
												RS2Gene.put(RSNum, Genes);
											}
											conn_Submit.disconnect();
										}
										catch(NullPointerException e){}
									}
									for(int g=0;g<Genes.size();g++)
									{
										if(Gene2Num.containsKey(Genes.get(g)))
										{
											ClosedGene=Genes.get(g);
											
											try 
											{
												URL url_Submit = new URL("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id=" + ClosedGene);
												HttpURLConnection conn_Submit = (HttpURLConnection) url_Submit.openConnection();
												conn_Submit.setDoOutput(true);
												conn_Submit.setRequestMethod("GET");
												int code = conn_Submit.getResponseCode();
												if(code == 200)
												{
													String STR="";
													String line="";
													BufferedReader br_Receive = new BufferedReader(new InputStreamReader(conn_Submit.getInputStream(), "UTF-8"));
													while((line = br_Receive.readLine()) != null)
													{
														STR=STR+line;
													}
													ptmp = Pattern.compile("<TaxID>([0-9]+)</TaxID>");
													mtmp = ptmp.matcher(STR);
													if(mtmp.find())
													{
														ClosedSpecies=mtmp.group(1);
													}
													RS2Gene.put(RSNum, Genes);
												}
												conn_Submit.disconnect();
											}
											catch(NullPointerException e){}
											
											break;
										}
									}
								}
								/*
								 *  find closed species
								 */
								int SpeciesClosedDistance=10000;
								if(ClosedSpecies.equals(""))
								{
									ClosedSpecies="9606";
									for(String Speciesid : SpeciesAnno.keySet())
									{
										if(!Blacklist_Species.containsKey(Speciesid))
										{
											for(String Varlocation : VariationAnno.get(Varid).keySet())
											{
												if(!Varlocation.equals("RS"))
												{
													String Var_anno[]=Varlocation.split("\t");
													int Var_paragraph_id=Integer.parseInt(Var_anno[0]);
													int Var_start=Integer.parseInt(Var_anno[1]);
													int Var_last=Integer.parseInt(Var_anno[2]);
													String Var_mention=Var_anno[3];
													
													for(String Specieslocation : SpeciesAnno.get(Speciesid).keySet())
													{
														String Species_anno[]=Specieslocation.split("\t");
														int Species_paragraph_id=Integer.parseInt(Species_anno[0]);
														int Species_start=Integer.parseInt(Species_anno[1]);
														int Species_last=Integer.parseInt(Species_anno[2]);
														String Species_mention=Species_anno[3];
														if(Var_paragraph_id == Species_paragraph_id) // paragraph the same
														{
															if(Var_start>Species_last) // ... Species ... Var ...
															{
																if(SpeciesClosedDistance>(Var_start-Species_last))
																{
																	SpeciesClosedDistance=Var_start-Species_last;
																	ClosedSpecies=Speciesid;
																}
															}
															else if(Species_start>Var_last && (!TablePassage.containsKey(Var_paragraph_id))) // ... Var ... Species ...
															{
																String betweenString=BC.PassageContexts.get(i).get(Var_paragraph_id).substring(Var_last, Species_start);
																Species_mention=Species_mention.replaceAll("[\\(\\)]", "\\.");
																if(!betweenString.matches(".*[a-z]\\. .*")) // Species is in the next sentence
																{
																	if(SpeciesClosedDistance>(Species_start-Var_last))
																	{
																		SpeciesClosedDistance=Species_start-Var_last;
																		ClosedSpecies=Speciesid;
																	}
																}
															}
														}
													}
												}
											}
										}
									}
								}
								/*
								 * Gene sequence location check
								 */
								for (int j = 0; j < BC.PassageNames.get(i).size(); j++)
								{
									ArrayList<String> Annotation = BC.Annotations.get(i).get(j); // Annotation
									for(int a=0;a<Annotation.size();a++)
									{
										String anno[]=Annotation.get(a).split("\t");
										String id="";
										if(anno.length==5){id=anno[4];}
										if(Varid.equals(id))
										{
											String SequenceCheck="";
											if(!ClosedGene.equals("")) // find closed gene
											{
												//Check sequence allele
												{
													String type="DNA";
													if(anno[3].equals("ProteinMutation"))
													{
														type="Protein";
													}
													Connection c = null;
													Statement stmt = null;
													try {
														Class.forName("org.sqlite.JDBC");
													} 
													catch ( Exception e ) 
													{
														System.err.println( e.getClass().getName() + ": " + e.getMessage() );
														System.exit(0);
													}
													c = DriverManager.getConnection("jdbc:sqlite:Database/refseq.db");
													stmt = c.createStatement();
													String SQL="SELECT seqid,Seq FROM refseq WHERE geneid='"+ClosedGene+"' and type='"+type+"' order by seqid desc";
													ResultSet data = stmt.executeQuery(SQL);
													while ( data.next() ) 
													{
														String component[]=Varid.split("\\|",-1);
														if(component.length>=5 && component[1].equals("SUB"))
														{
															String W=component[2];
															String P=component[3];
															String M=component[4];
															P=P.replaceAll("^(IVS|EX)[0-9IV]+[\\+\\-]*", "");
															if(W.matches("[A-Z]") && M.matches("[A-Z]") && P.matches("[0-9]+") && data.getString("Seq").length()>Integer.parseInt(P))
															{
																if(data.getString("Seq").substring(Integer.parseInt(P),Integer.parseInt(P)+1).equals(W))
																{
																	SequenceCheck=data.getString("seqid")+"|Matched-W";
																	break;
																}
																else if(data.getString("Seq").substring(Integer.parseInt(P),Integer.parseInt(P)+1).equals(M))
																{
																	SequenceCheck=data.getString("seqid")+"|Matched-M";
																	break;
																}
																if(Integer.parseInt(P)>0 && data.getString("Seq").substring(Integer.parseInt(P)-1,Integer.parseInt(P)).equals(W))
																{
																	SequenceCheck=data.getString("seqid")+"|PlusMatched-W";
																	break;
																}
																else if(Integer.parseInt(P)>0 && data.getString("Seq").substring(Integer.parseInt(P)-1,Integer.parseInt(P)).equals(M))
																{
																	SequenceCheck=data.getString("seqid")+"|PlusMatched-M";
																	break;
																}
															}
														}
														if(component.length>=4 && component[1].matches("(DEL|INS)"))
														{
															String P=component[2];
															String M=component[3];
															P=P.replaceAll("^(IVS|EX)[0-9IV]+[\\+\\-]*", "");
															if(M.matches("[A-Z]") && P.matches("[0-9]+") && data.getString("Seq").length()>Integer.parseInt(P))
															{
																if(data.getString("Seq").substring(Integer.parseInt(P),Integer.parseInt(P)+1).equals(M))
																{
																	SequenceCheck=data.getString("seqid")+"|Matched-M";
																	break;
																}
																else if(data.getString("Seq").substring(Integer.parseInt(P)-1,Integer.parseInt(P)).equals(M))
																{
																	SequenceCheck=data.getString("seqid")+"|PlusMatched-M";
																	break;
																}
															}
														}
														else
														{
															//Give Up
														}
													}
													stmt.close();
													c.close();
												}
											}
											
											String ClosedSpeciesSTR="";
											ClosedSpecies=ClosedSpecies.replaceAll(";", "|");
											if((!ClosedSpecies.equals("9606")) && SpeciesClosedDistance<=50){ClosedSpeciesSTR=";CorrespondingSpecies:"+ClosedSpecies;} // find closed species //+"("+SpeciesClosedDistance+")"
											String CorrespondingGeneSTR="";
											ClosedGene=ClosedGene.replaceAll(";", "|");
											if((!ClosedGene.equals(""))){CorrespondingGeneSTR=";CorrespondingGene:"+ClosedGene;}
											String SequenceCheckSTR="";
											if((!SequenceCheck.equals(""))){SequenceCheckSTR=";"+SequenceCheck;}
											
											BC.Annotations.get(i).get(j).set(a, Annotation.get(a)+CorrespondingGeneSTR+SequenceCheckSTR+ClosedSpeciesSTR);
										}
									}
								}
							}
						}
						BC.BioCOutput(InputFolder+"/"+InputFile,OutputFolder+"/"+InputFile);
						
						/*
						 * Time stamp - last
						 */
						endTime = System.currentTimeMillis();//ending time
						totTime = endTime - startTime;
						System.out.println(InputFile+" - ("+Format+" format) : Processing Time:"+totTime/1000+"sec");
					}
				}
			}
		}
	}
}
