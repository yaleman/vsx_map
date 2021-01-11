# VSX Parser

Can't make sense of your VSX environment? Me either. 

This takes the output of the following command from checkpoint VSX clusters and puts it all together and tries to make sense of it:

    vsx stat -v && cphaprob stat && cphaprob -a if

Put the output in files in the "input_dir" folder and it'll parse them. I haven't worked on this for a while, but there's a whole file naming convention and stuff.