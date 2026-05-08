package db;
//
// https://bitbucket.org/xerial/sqlite-jdbc/downloads --> sqlite-jdbc-3.8.11.2.jar
// Add to build path
//

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.sql.*;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;

public class Mapping2Dictionary
{
	
	public static void search() throws IOException, InterruptedException, SQLException
	{
		HashMap<String,String> one2three = new HashMap<String,String>();
		one2three.put("A", "Ala");
		one2three.put("R", "Arg");
		one2three.put("N", "Asn");
		one2three.put("D", "Asp");
		one2three.put("C", "Cys");
		one2three.put("Q", "Gln");
		one2three.put("E", "Glu");
		one2three.put("G", "Gly");
		one2three.put("H", "His");
		one2three.put("I", "Ile");
		one2three.put("L", "Leu");
		one2three.put("K", "Lys");
		one2three.put("M", "Met");
		one2three.put("F", "Phe");
		one2three.put("P", "Pro");
		one2three.put("S", "Ser");
		one2three.put("T", "Thr");
		one2three.put("W", "Trp");
		one2three.put("Y", "Tyr");
		one2three.put("V", "Val");
		one2three.put("B", "Asx");
		one2three.put("Z", "Glx");
		one2three.put("X", "Xaa");
		one2three.put("X", "Ter");
		
		HashMap<String,String> Variation_RS = new HashMap<String,String>();
		BufferedWriter OutputFile = new BufferedWriter(new OutputStreamWriter(new FileOutputStream("lib/RegEx/Mutation_RS_Geneid_rev.txt"), "UTF-8"));
		BufferedReader PAM = new BufferedReader(new InputStreamReader(new FileInputStream("lib/RegEx/Mutation_RS_Geneid.txt"), "UTF-8"));
		String line="";
		while ((line = PAM.readLine()) != null)  
		{
			//Pattern	c|SUB|C|1749|T	2071558	269
			String nt[]=line.split("\t");
			String type=nt[0];
			String Variation=nt[1];
			String RS=nt[2];
		
			String component[]=Variation.split("\\|");
			String NormalizedForm="";
			String NormalizedForm_reverse="";
			String NormalizedForm_plus1="";
			String NormalizedForm_minus1="";
			if(component.length>=3)
			{
				if(component[1].equals("SUB"))
				{
					if(component[0].equals("p"))
    				{
						String tmp="";
						/*one -> three*/
						for(int len=0;len<component[2].length();len++)
						{
							if(one2three.containsKey(component[2].substring(len, len+1)))
							{
								tmp = tmp + one2three.get(component[2].substring(len, len+1));
							}
						}
						component[2]=tmp;
						tmp="";
						for(int len=0;len<component[4].length();len++)
						{
							if(one2three.containsKey(component[4].substring(len, len+1)))
							{
								tmp = tmp + one2three.get(component[4].substring(len, len+1));		        							
							}
						}
						component[4]=tmp;
						
						if(component[2].equals(component[4]))
						{
							NormalizedForm=component[0]+"."+component[2]+component[3]+"=";
						}
						else
						{
    						NormalizedForm=component[0]+"."+component[2]+component[3]+component[4];
    						NormalizedForm_reverse=component[0]+"."+component[4]+component[3]+component[2];
						}
    					String wildtype[]=component[2].split(",");
    					String mutant[]=component[4].split(",");
    					for (int i=0;i<wildtype.length;i++) //May have more than one pair
    					{
    						for (int j=0;j<mutant.length;j++)
        					{
    							NormalizedForm=NormalizedForm+"|"+component[0]+"."+wildtype[i]+component[3]+mutant[j];
        					}
    					}
    				}
					else //[rmgc]
					{
						if(component.length>4)
        				{
    						component[3]=component[3].replaceAll("^\\+", "");
    						NormalizedForm=component[0]+"."+component[3]+component[2]+">"+component[4];
    						NormalizedForm_reverse=component[0]+"."+component[3]+component[4]+">"+component[2];
    						if(component[3].matches("[\\+\\-]{0,1}[0-9]{1,8}"))
    						{
        						NormalizedForm_plus1=component[0]+"."+(Integer.parseInt(component[3])+1)+""+component[2]+">"+component[4];
        						NormalizedForm_minus1=component[0]+"."+(Integer.parseInt(component[3])-1)+""+component[2]+">"+component[4];
    						}
        					String wildtype[]=component[2].split(",");
        					String mutant[]=component[4].split(",");
        					for (int i=0;i<wildtype.length;i++) //May have more than one pair
        					{
        						for (int j=0;j<mutant.length;j++)
	        					{
        							NormalizedForm=NormalizedForm+"|"+component[0]+"."+component[3]+wildtype[i]+">"+mutant[j];
	        					}
        					}
        				}
    				}
				}
				else if(component[1].equals("DEL"))
				{
					if(component.length>3)
					{
						if(component[0].equals("p"))
        				{
    						String tmp="";
    						for(int len=0;len<component[3].length();len++)
    						{
    							tmp = tmp + one2three.get(component[3].substring(len, len+1));
    						}
    						component[3]=tmp;
    					}
    					NormalizedForm=component[0]+"."+component[2]+"del"+component[3];
					}
					NormalizedForm=NormalizedForm+"|"+component[0]+"."+component[2]+"del";
				}
				else if(component[1].equals("INS"))
				{
					if(component.length>3)
					{
						if(component[0].equals("p"))
        				{
    						String tmp="";
    						for(int len=0;len<component[3].length();len++)
    						{
    							tmp = tmp + one2three.get(component[3].substring(len, len+1));
    						}
    						component[3]=tmp;
    					}
    					NormalizedForm=component[0]+"."+component[2]+"ins"+component[3];
					}
					NormalizedForm=NormalizedForm+"|"+component[0]+"."+component[2]+"ins";
				}
				else if(component[1].equals("INDEL"))
				{
					if(component.length>3)
					{
						//c.*2361_*2362delAAinsA
    					//c.2153_2155delinsTCCTGGTTTA
    					if(component[0].equals("p"))
        				{
    						String tmp="";
    						for(int len=0;len<component[3].length();len++)
    						{
    							tmp = tmp + one2three.get(component[3].substring(len, len+1));
    						}
    						component[3]=tmp;
    					}
    					NormalizedForm=component[0]+"."+component[2]+"delins"+component[3];
					}
				}
				else if(component[1].equals("DUP"))
				{
					if(component.length>3)
					{
						if(component[0].equals("p"))
        				{
    						String tmp="";
    						for(int len=0;len<component[3].length();len++)
    						{
    							tmp = tmp + one2three.get(component[3].substring(len, len+1));
    						}
    						component[3]=tmp;
    					}
    					NormalizedForm=component[0]+"."+component[2]+"dup"+component[3];
					}
					NormalizedForm=NormalizedForm+"|"+component[0]+"."+component[2]+"dup";
				}
				else if(component[1].equals("FS"))
				{
					if(component[0].equals("p"))
    				{
						String tmp="";
						for(int len=0;len<component[2].length();len++)
						{
							tmp = tmp + one2three.get(component[2].substring(len, len+1));
						}
						component[2]=tmp;
						
						tmp="";
						if(component.length>=5)
						{
    						for(int len=0;len<component[4].length();len++)
    						{
    							tmp = tmp + one2three.get(component[4].substring(len, len+1));
    						}
    						component[4]=tmp;
						}
					}
					
					if(component.length>=5)
					{
						NormalizedForm=component[0]+"."+component[2]+component[3]+component[4]+"fs";
					}
					else if(component.length==4)
					{
						NormalizedForm=component[0]+"."+component[2]+component[3]+"fs";
					}
				}
			}
			
			String NormalizedForms[]=NormalizedForm.split("\\|");
			HashMap<String,String> NormalizedForm_hash = new HashMap<String,String>();
			for(int n=0;n<NormalizedForms.length;n++)
			{
				NormalizedForm_hash.put(NormalizedForms[n], "");
			}
			NormalizedForm="";
			for(String NF : NormalizedForm_hash.keySet())
			{
				if(NormalizedForm.equals(""))
				{
					NormalizedForm=NF;
				}
				else
				{
					NormalizedForm=NormalizedForm+"|"+NF;
				}
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

			String DB="var2rs_c";
			String Table="var2rs_c";
			if(component[0].equals("p"))
			{	
				DB="var2rs_p";
				Table="var2rs_p";
			}
			else if(component[0].equals("c"))
			{	
				DB="var2rs_c.Nprefix";
				Table="var2rs_c";
			}
			else if(component[0].equals("r"))
			{	
				DB="var2rs_c";
				Table="var2rs_c";
			}
			else if(component[0].equals("m"))
			{	
				DB="var2rs_m";
				Table="var2rs_m";
			}
			else if(component[0].equals("n"))
			{	
				DB="var2rs_n";
				Table="var2rs_n";
			}
			else if(component[0].equals("g"))
			{	
				DB="var2rs_g";
				Table="var2rs_g";
			}
			
			//NormalizedForm
			c = DriverManager.getConnection("jdbc:sqlite:Database/"+DB+".db");
			stmt = c.createStatement();
			String NormalizedForm_arr[]=NormalizedForm.split("\\|");
			String SQL="SELECT rs FROM "+Table+" WHERE ";
			for(int nfa=0;nfa<NormalizedForm_arr.length;nfa++)
			{
				SQL=SQL+"var='"+NormalizedForm_arr[nfa]+"' or ";
			}
			SQL=SQL.replaceAll(" or $", "");
			ResultSet rs = stmt.executeQuery(SQL);
			boolean Found=false;
			while ( rs.next() ) 
			{
				if(rs.getString("rs").matches(".*\\|"+RS+"\\|.*"))
				{
					Found=true;
				}
				else if(rs.getString("rs").matches("^"+RS+"\\|.*"))
				{
					Found=true;
				}
				else if(rs.getString("rs").matches(".*\\|"+RS+"$"))
				{
					Found=true;
				}
			}
			stmt.close();
			c.close();
			if(Found == true)
			{
				OutputFile.write(line+"\tDictionaryMatch\n");
			}
			else
			{
				OutputFile.write(line+"\n");
			}
		}
		OutputFile.close();
	}
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		search();
	}
}
